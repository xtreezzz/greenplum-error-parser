import unittest
from src.greenplum_parser import split_arguments, find_function_calls, extract_ereport, extract_elog, clean_errmsg_template, errcode_mapping

class TestGreenplumParser(unittest.TestCase):

    def test_split_arguments_simple(self):
        argument_string = 'ERRCODE_FILE_NOT_FOUND, "File not found: %s", filePath'
        expected = ['ERRCODE_FILE_NOT_FOUND', '"File not found: %s"', 'filePath']
        result = split_arguments(argument_string)
        self.assertEqual(result, expected)

    def test_split_arguments_nested(self):
        argument_string = 'ERRCODE_SYNTAX_ERROR, "Syntax error near \'%%s\'", token'
        expected = ['ERRCODE_SYNTAX_ERROR', '"Syntax error near \'%%s\'"', 'token']
        result = split_arguments(argument_string)
        self.assertEqual(result, expected)

    def test_find_function_calls(self):
        s = 'errmsg("An error occurred: %s", errorMsg), errcode(ERRCODE_INTERNAL_ERROR)'
        func_names = ['errmsg', 'errcode']
        expected = [
            {'func_name': 'errmsg', 'args_str': '"An error occurred: %s", errorMsg'},
            {'func_name': 'errcode', 'args_str': 'ERRCODE_INTERNAL_ERROR'}
        ]
        result = find_function_calls(s, func_names)
        self.assertEqual(result, expected)

    def test_extract_ereport(self):
        log = 'ereport(ERROR, errmsg("File not found: %s", filePath), errcode(ERRCODE_FILE_NOT_FOUND));'
        expected = {
            'severity_level': 'ERROR',
            'errmsg_template': 'File not found: %s',
            'errmsg_variables': ['filePath'],
            'errcode': 'ERRCODE_FILE_NOT_FOUND',
            'errcode_numeric': errcode_mapping.get('ERRCODE_FILE_NOT_FOUND', None)
        }
        result = extract_ereport(log)
        self.assertEqual(result['severity_level'], expected['severity_level'])
        self.assertEqual(result['errmsg_template'], expected['errmsg_template'])
        self.assertEqual(result['errmsg_variables'], expected['errmsg_variables'])
        self.assertEqual(result['errcode'], expected['errcode'])
        self.assertEqual(result['errcode_numeric'], expected['errcode_numeric'])

    def test_extract_elog(self):
        log = 'elog(INFO, "Starting process with ID: %d", processId);'
        expected = {
            'severity_level': 'INFO',
            'errmsg_template': 'Starting process with ID: %d',
            'errmsg_variables': ['processId'],
            'errcode': None,
            'errcode_numeric': None
        }
        result = extract_elog(log)
        self.assertEqual(result, expected)

    def test_clean_errmsg_template(self):
        template = 'File not found: %s\\nPlease check the path.'
        expected = 'File not found: Please check the path.'
        result = clean_errmsg_template(template)
        self.assertEqual(result, expected)

if __name__ == '__main__':
    unittest.main()
