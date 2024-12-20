# Greenplum Error Parser

This project is designed to extract error information from Greenplum source code by parsing logging statements. The parser correctly handles escape sequences in error messages and includes line numbers in the output, providing precise locations of errors within the source code. The results are saved in JSON format for further analysis or integration with other tools.

## Contents

- [Features](#features)
- [Unified JSON Schema](#unified-json-schema)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- Parses Greenplum source files to extract logging statements.
- Extracts detailed error information, including:
  - **File path with line numbers** (e.g., `src/backend/catalog/pg_publication.c:82`)
  - Error code and error code name
  - Error class name (severity level)
  - **Correctly handles escape sequences** in error messages
  - Error message template and variables
- Outputs data in a unified JSON schema for consistency and ease of use.

## Unified JSON Schema

```json
{
  "errors": [
    {
      "file_path": "string",  // Includes line number, e.g., 'src/backend/catalog/pg_publication.c:82'
      "error_code": "string or number",
      "error_code_name": "string",
      "error_class_name": "string",
      "error_message_template": "string",
      "error_message_variables": ["array of strings"],
      "severity_level": "string",
      "original_text": "string"
    }
  ]
}
```

## Requirements

- Python 3.6 or higher
- Greenplum source code available locally
  - You can obtain the Greenplum source code from the [Greenplum Database Archive](https://github.com/greenplum-db/gpdb-archive).

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/xtreezzz/greenplum-error-parser.git
   ```

2. **Navigate to the project directory:**

   ```bash
   cd greenplum-error-parser
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

   *Note: Currently, there are no external dependencies. If you add any, list them in `requirements.txt`.*

## Usage

Run the parsing script by specifying the path to the Greenplum source code and the desired output JSON file path:

```bash
python src/greenplum_parser.py -s /path/to/greenplum/source -o data/errors_greenplum.json
```

- `-s`, `--source_directory`: **(Required)** Path to the Greenplum source code directory.
- `-o`, `--output_file`: **(Optional)** Path to the output JSON file. Default is `data/errors_greenplum.json`.

### **Example Command**

```bash
python src/greenplum_parser.py -s ~/gpdb-archive -o data/errors_greenplum.json
```

This command parses the Greenplum source code located at `~/gpdb-archive` and saves the extracted error information to `data/errors_greenplum.json`.

To download the Greenplum Database Archive, you can clone it from GitHub:

```bash
git clone https://github.com/greenplum-db/gpdb-archive.git
```

## Examples

After running the parser, the `data/errors_greenplum.json` file will contain structured error information like the following:

```json
{
  "errors": [
    {
      "file_path": "src/backend/catalog/pg_publication.c:82",
      "error_code": "22023",
      "error_code_name": "ERRCODE_INVALID_PARAMETER_VALUE",
      "error_class_name": "ERROR",
      "error_message_template": "table \"%s\" cannot be replicated",
      "error_message_variables": [
        "RelationGetRelationName(targetrel)"
      ],
      "severity_level": "ERROR",
      "original_text": "ereport(ERROR,\n\t\t\t\t(errcode(ERRCODE_INVALID_PARAMETER_VALUE),\n\t\t\t\t errmsg(\"table \\\"%s\\\" cannot be replicated\",\n\t\t\t\t\t\tRelationGetRelationName(targetrel)),\n\t\t\t\t errdetail(\"Temporary and unlogged relations cannot be replicated.\")))"
    }
    // More error entries...
  ]
}
```

Note:
- The `error_message_template` correctly handles escape sequences, matching the original source code.
- The `file_path` includes the line number, providing precise location of the error.

## Project Structure

```
greenplum-error-parser/
├── src/
│   └── greenplum_parser.py          # Main parser script
├── data/
│   ├── errcode_mapping.json         # External error code mapping
│   ├── errors_greenplum.json        # Output JSON file (created after running the parser)
│   ├── error_templates_greenplum.json  # Unique error templates
│   └── entries_with_null_errmsg_template_greenplum.json  # Entries with null 'errmsg_template'
├── tests/
│   └── test_greenplum_parser.py     # Unit tests
├── README.md                         # Project documentation
├── LICENSE                           # Project license
└── requirements.txt                  # Python dependencies
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

1. Fork the repository.
2. Create your feature branch: `git checkout -b feature/your-feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Open a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.