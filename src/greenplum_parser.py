import os
import re
import json
import argparse
import ast
from collections import defaultdict

def load_errcode_mapping(mapping_file='data/errcode_mapping.json'):
    """
    Loads errcode_mapping from an external JSON file.
    """
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading errcode_mapping: {e}")
        return {}

errcode_mapping = load_errcode_mapping()

def remove_comments(code):
    """
    Removes comments from the code.
    """
    # Remove single-line comments
    code = re.sub(r'//.*', '', code)
    code = re.sub(r'#.*', '', code)
    # Remove multi-line comments
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    return code

def extract_logging_statements(code):
    """
    Extracts logging statements from the code, along with their line numbers.
    """
    log_functions = ['elog', 'ereport']
    pattern = re.compile(r'\b(' + '|'.join(log_functions) + r')\b\s*\(')

    statements = []
    index = 0
    length = len(code)

    # Build a list of line start positions
    line_starts = [0]
    for m in re.finditer('\n', code):
        line_starts.append(m.end())

    # Function to get line number from index
    def get_line_number(pos):
        # Binary search to find the line number efficiently
        left, right = 0, len(line_starts) - 1
        while left <= right:
            mid = (left + right) // 2
            if line_starts[mid] <= pos:
                left = mid + 1
            else:
                right = mid - 1
        return right + 1  # Line numbers start at 1

    while index < length:
        match = pattern.search(code, index)
        if not match:
            break
        start_index = match.start()
        base_line_number = get_line_number(start_index)
        paren_count = 1  # Already found the first '('
        i = match.end()
        while i < length and paren_count > 0:
            char = code[i]
            if char == '(':
                paren_count += 1
            elif char == ')':
                paren_count -= 1
            elif char == '"' and (i == 0 or code[i - 1] != '\\'):
                # Skip strings to avoid miscounting parentheses
                i += 1
                while i < length and (i < length) and (code[i] != '"' or code[i - 1] == '\\'):
                    i += 1
            i += 1
        end_index = i
        statement = code[start_index:end_index]

        # Checking for parser_errposition
        parser_pos = statement.find('parser_errposition')
        if parser_pos != -1:
            global_parser_pos = start_index + parser_pos
            line_number = get_line_number(global_parser_pos)
        else:
            line_number = base_line_number

        statements.append((statement, line_number))
        index = end_index
    return statements

def preprocess_log(log):
    """
    Preprocesses the log by removing newline escape characters and handling escaped quotes.
    """
    log = log.replace('\\n', '')  # Remove newline escapes
    log = log.replace('\\r\\n', '')
    # Handle escaped backslashes
    log = log.replace('\\\\', '\\')
    return log

def split_arguments(s):
    """
    Splits the argument string into a list, considering nested parentheses, quotes, and escaped characters.
    """
    args = []
    current_arg = ''
    depth = 0
    ternary_depth = 0
    in_string = False
    escape = False
    i = 0
    while i < len(s):
        c = s[i]
        if escape:
            current_arg += c
            escape = False
        elif c == '\\':
            current_arg += c
            escape = True
        elif in_string:
            current_arg += c
            if c == '"':
                in_string = False
        else:
            if c == '"':
                current_arg += c
                in_string = True
            elif c == '(':
                current_arg += c
                depth += 1
            elif c == ')':
                current_arg += c
                if depth > 0:
                    depth -= 1
            elif c == '?':
                current_arg += c
                ternary_depth += 1
            elif c == ':':
                current_arg += c
                if ternary_depth > 0:
                    ternary_depth -= 1
            elif c == ',' and depth == 0 and ternary_depth == 0:
                args.append(current_arg.strip())
                current_arg = ''
            else:
                current_arg += c
        i += 1
    if current_arg.strip():
        args.append(current_arg.strip())
    return args

def find_function_calls(s, func_names):
    """
    Finds all function calls in the string s with names from func_names.
    Returns a list of dictionaries with 'func_name' and 'args_str'.
    """
    results = []
    pattern = re.compile(r'(' + '|'.join(func_names) + r')\s*\(')
    i = 0
    length = len(s)
    while i < length:
        match = pattern.search(s, i)
        if not match:
            break
        func_name = match.group(1)
        start = match.end()
        paren_count = 1
        pos = start
        while pos < length and paren_count > 0:
            if s[pos] == '(':
                paren_count += 1
            elif s[pos] == ')':
                paren_count -= 1
            elif s[pos] == '"' and (pos == 0 or s[pos - 1] != '\\'):
                # Handle strings to avoid counting parentheses within strings
                pos += 1
                while pos < length and (s[pos] != '"' or s[pos - 1] == '\\'):
                    pos += 1
            pos += 1
        args_str = s[start:pos - 1]  # Exclude the closing ')'
        results.append({'func_name': func_name, 'args_str': args_str})
        i = pos
    return results

def extract_ereport(log):
    """
    Extracts information from ereport logs.
    """
    log = log.strip()
    if not log.startswith('ereport'):
        return None
    # Remove 'ereport(' from the start and ')' from the end
    content = log[len('ereport'):].strip()
    if content.startswith('(') and content.endswith(')'):
        content = content[1:-1]
    else:
        return None
    # Split arguments
    args = split_arguments(content)
    if len(args) < 2:
        return None
    severity_level = args[0].strip()
    error_spec = ','.join(args[1:])  # Rejoin the remaining arguments into a string
    # Find function calls within error_spec
    errmsg_functions = ['errmsg', 'errmsg_internal', 'errmsg_plural']
    errcode_functions = ['errcode', 'errcode_for_file_access']
    all_functions = errmsg_functions + errcode_functions + ['errdetail', 'errhint', 'errcontext']
    functions = find_function_calls(error_spec, all_functions)
    # Process functions to extract errmsg_template and errcode
    errmsg_template = None
    errmsg_variables = []
    errcode = None
    errcode_numeric = None
    for func in functions:
        if func['func_name'] in errmsg_functions:
            args = split_arguments(func['args_str'])
            if args:
                errmsg_template_raw = args[0].strip()
                if errmsg_template_raw.startswith('"') and errmsg_template_raw.endswith('"'):
                    errmsg_template_raw = errmsg_template_raw[1:-1]
                    try:
                        errmsg_template = ast.literal_eval('"' + errmsg_template_raw + '"')
                    except Exception:
                        errmsg_template = errmsg_template_raw
                else:
                    errmsg_template = errmsg_template_raw
                # Variables start from the second argument
                if len(args) > 1:
                    errmsg_variables = args[1:]
        elif func['func_name'] in errcode_functions:
            errcode_arg = func['args_str'].strip()
            errcode = errcode_arg
            if errcode.startswith('ERRCODE_'):
                errcode_numeric = errcode_mapping.get(errcode, None)
    return {
        'severity_level': severity_level,
        'errmsg_template': errmsg_template,
        'errmsg_variables': errmsg_variables,
        'errcode': errcode,
        'errcode_numeric': errcode_numeric
    }

def extract_elog(log):
    """
    Extracts information from elog logs using regular expressions.
    """
    pattern = re.compile(
        r'elog\s*\(\s*(.*?)\s*,\s*(.*)\s*\)$',
        re.DOTALL
    )
    match = pattern.search(log)
    if match:
        severity_level = match.group(1).strip()
        args_content = match.group(2).strip()

        args = split_arguments(args_content)
        if args:
            errmsg_template_raw = args[0].strip()
            if errmsg_template_raw.startswith('"') and errmsg_template_raw.endswith('"'):
                errmsg_template_raw = errmsg_template_raw[1:-1]
                try:
                    errmsg_template = ast.literal_eval('"' + errmsg_template_raw + '"')
                except Exception:
                    errmsg_template = errmsg_template_raw
            else:
                errmsg_template = errmsg_template_raw
            errmsg_variables = args[1:] if len(args) > 1 else []
        else:
            errmsg_template = None
            errmsg_variables = []

        return {
            'severity_level': severity_level,
            'errmsg_template': errmsg_template,
            'errmsg_variables': errmsg_variables,
            'errcode': None,
            'errcode_numeric': None
        }
    return None

def clean_errmsg_template(errmsg_template):
    """
    Cleans the errmsg_template by removing format specifiers, escaped characters,
    and quotes without removing spaces between words.
    """
    if errmsg_template is None:
        return None

    # Pattern to remove C-style format specifiers (%s, %d, %.*s, etc.)
    pattern = r'%(?:\d+\$)?[+-]?(?:0| )?(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|j|z|t|L)?[diuoxXfFeEgGaAcCsSpn%]'

    # Remove format specifiers
    cleaned = re.sub(pattern, '', errmsg_template)

    # Remove escaped characters (\n, \t, \r)
    cleaned = re.sub(r'\\[nrt]', '', cleaned)

    # Remove quotes
    cleaned = cleaned.replace('"', '').replace("'", '')

    # Remove double spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Strip leading and trailing spaces
    cleaned = cleaned.strip()

    return cleaned

def extract_info_from_log(log):
    """
    Determines the type of log and extracts information accordingly.
    """
    log = preprocess_log(log)

    if log.strip().startswith('ereport'):
        ereport_info = extract_ereport(log)
        if ereport_info:
            errmsg_clean = None
            if ereport_info['errmsg_template']:
                errmsg_clean = clean_errmsg_template(ereport_info['errmsg_template'])
            return {
                'log': log,
                'severity_level': ereport_info['severity_level'],
                'errmsg_template': ereport_info['errmsg_template'],
                'errmsg_variables': ereport_info['errmsg_variables'],
                'errcode': ereport_info['errcode'],
                'errcode_numeric': ereport_info['errcode_numeric'],
                'errmsg_clean': errmsg_clean,
                'script_parse_error': None
            }
        else:
            return {
                'log': log,
                'severity_level': None,
                'errmsg_template': None,
                'errmsg_variables': None,
                'errcode': None,
                'errcode_numeric': None,
                'errmsg_clean': None,
                'script_parse_error': 'Failed to parse ereport log'
            }
    elif log.strip().startswith('elog'):
        elog_info = extract_elog(log)
        if elog_info:
            errmsg_clean = None
            if elog_info['errmsg_template']:
                errmsg_clean = clean_errmsg_template(elog_info['errmsg_template'])
            return {
                'log': log,
                'severity_level': elog_info['severity_level'],
                'errmsg_template': elog_info['errmsg_template'],
                'errmsg_variables': elog_info['errmsg_variables'],
                'errcode': None,
                'errcode_numeric': None,
                'errmsg_clean': errmsg_clean,
                'script_parse_error': None
            }
        else:
            return {
                'log': log,
                'severity_level': None,
                'errmsg_template': None,
                'errmsg_variables': None,
                'errcode': None,
                'errcode_numeric': None,
                'errmsg_clean': None,
                'script_parse_error': 'Failed to parse elog log'
            }
    else:
        return {
            'log': log,
            'severity_level': None,
            'errmsg_template': None,
            'errmsg_variables': None,
            'errcode': None,
            'errcode_numeric': None,
            'errmsg_clean': None,
            'script_parse_error': 'Unknown log type'
        }

def main():
    """
    Main function to parse logging statements from the source code and save the results.
    """
    parser = argparse.ArgumentParser(description='Parse logging statements from Greenplum source code.')
    parser.add_argument('-s', '--source_directory', required=True, help='Path to the Greenplum source code directory.')
    parser.add_argument('-o', '--output_file', default='data/errors_greenplum.json', help='Path to the output JSON file.')
    args = parser.parse_args()

    directory = args.source_directory
    output_file = args.output_file

    # Initialize structure to store results
    file_logging_statements = defaultdict(list)

    # Walk through the directory and extract logging statements
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith(('.c', '.cpp', '.h', '.hpp', '.py', '.pl', '.go', '.sql')):
                filepath = os.path.join(root, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        code = f.read()
                        code = remove_comments(code)
                        statements_with_lines = extract_logging_statements(code)
                        if statements_with_lines:
                            file_logging_statements[filepath].extend(statements_with_lines)
                except Exception as e:
                    print(f"Failed to process {filepath}: {e}")

    # Initialize list for results
    parsed_logs = []

    # Parse each logging statement
    for filepath, statements in file_logging_statements.items():
        for stmt, line_number in statements:
            info = extract_info_from_log(stmt)
            # Change file path to relative to directory and include line number
            relative_path = os.path.relpath(filepath, directory)
            relative_path = relative_path.replace('\\', '/')  # Replace backslashes with forward slashes
            info['file_path'] = f"{relative_path}:{line_number}"  # Add line number to file path
            parsed_logs.append(info)

    # Prepare list of errors for JSON
    errors = []
    for log in parsed_logs:
        # Ensure no parsing errors and there's an error message template
        if log['script_parse_error'] is None and log['errmsg_template'] is not None:
            error_entry = {
                'file_path': log['file_path'],
                'error_code': log['errcode_numeric'] if log['errcode_numeric'] is not None else log['errcode'],
                'error_code_name': log['errcode'],
                'error_class_name': log['severity_level'],
                'error_message_template': log['errmsg_template'],
                'error_message_variables': log['errmsg_variables'],
                'severity_level': log['severity_level'],
                'original_text': log['log']
            }
            errors.append(error_entry)

    # Save all errors to a single JSON file
    output_data = {
        "errors": errors
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    # Print summary information
    total_logs = len(parsed_logs)
    total_errors = len(errors)
    print(f"Total logging statements: {total_logs}")
    print(f"Total errors found: {total_errors}")
    print(f"Errors saved to '{output_file}'.")

    # Create a list of unique error templates
    error_templates = list(set([log['error_message_template'] for log in errors if log['error_message_template']]))

    # Save unique templates to a file
    templates_file = 'data/error_templates_greenplum.json'
    with open(templates_file, 'w', encoding='utf-8') as f:
        json.dump(error_templates, f, ensure_ascii=False, indent=4)

    print(f"Unique error templates saved to '{templates_file}'.")

    # Save all entries where 'errmsg_template' is None to a separate file
    entries_with_null_errmsg_template = [log for log in parsed_logs if log['errmsg_template'] is None]

    # Save these entries to a file
    null_entries_file = 'data/entries_with_null_errmsg_template_greenplum.json'
    with open(null_entries_file, 'w', encoding='utf-8') as f:
        json.dump(entries_with_null_errmsg_template, f, ensure_ascii=False, indent=4)

    print(f"Entries with 'errmsg_template' as null saved to '{null_entries_file}'.")

if __name__ == "__main__":
    main()
