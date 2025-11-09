# Okdesk API Client Generator
A Python-based tool that automatically generates a fully functional Okdesk API client from the official documentation. This project parses the Okdesk API documentation and creates a ready-to-use Python client with intuitive class hierarchy and method signatures.

## Features
-  **Automatic Client Generation**: Creates complete Python client from Okdesk API documentation
-  **Multi-language Support**: Works with any language version of the documentation (uses English for code generation)
-  **Intuitive Structure**: Organizes endpoints into logical classes matching API sections
-  **Error Handling**: Built-in exception handling for API errors
-  **Authentication**: Automatic token management and session handling

## Project Structure
okdesk-api-client-generator/
├── okdesk_client_generator.py # Main client generator module
├── api_parser.py # Documentation parser and data extractor
├── template.jinja # Jinja2 template for client code generation
├── requirements.txt # Requirements
└── README.md # This file

## Installation
1. Clone the repository:
```bash
git  clone  https://github.com/your-username/okdesk-client-generator.git
cd  okdesk-client-generator
```
2. Install and activate the virtual environment:

Windows
```bash
python  -m  venv  venv
source venv/Scripts/activate
```
Linux
```bash
python3  -m  venv  venv
source env/bin/activate
```
3. Install required dependencies:
Windows
```bash
python -m pip install -U pip
pip install -r requirements.txt
```
Linux
```bash
python3 -m pip install -U pip
pip install -r requirements.txt
```

## Usage
Import the function and pass the URL to the Okdesk API documentation as an argument. If no argument is provided, the default URL will be used.
```python
from okdesk_client_generator import create_okdesk_api_client

create_okdesk_api_client("https://apidocs.okdesk.com/apidoc")
```

## Using the Generated Client
```python
from okdesk_api_client import OkdeskAPI

client = OkdeskAPI("your_company_account", "your_login", "your_password")
```
## Use API methods
 Receiving agents groups
```python
list_of_groups = okdesk_api.employees.receiving_agents_groups()
```
Obtaining detailed list by parameters
```python
params = {
    "created_since": "22-03-2025 15:30",
    "created_until": "22-06-2025 18:00",
    "assignee_ids": [5],
    "page[number]": 2,
    "page[size]": 30
}
my_tickets = okdesk_api.tickets.obtaining_detailed_list_by_parameters(params)
```

## How It Works
The `api_parser.py` module extracts and analyzes the HTML structure of the Okdesk API documentation.
The `okdesk_client_generator.py` module processes this data and uses the `template.jinja` template to generate Python code. It creates the `okdesk_api_client.py` file, where:
-   Each API section is represented by its own class.
-   Endpoints are represented as methods of these classes.
-  A main client class is also provided, which brings all the section classes together into a unified whole and handles authentication.

## Requirements
- Python 3.11+
- requests
- beautifulsoup4
- jinja2

## Acknowledgments
Module descriptions and documentation were prepared with AI assistance

## Disclaimer
This tool is not officially affiliated with Okdesk. It is a utility developed by sinerslb to simplify working with the Okdesk API. Always refer to the official Okdesk documentation for up-to-date information on API specifications.

The automatically generated client code is based on the official Okdesk API documentation and may require updates if the API changes.