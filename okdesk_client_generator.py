"""
Okdesk API Client Generator

This module provides functionality to generate a complete Python client for
the Okdesk API based on parsed documentation structure. The generator
transforms structured API data into ready-to-use Python code using Jinja2
templates, creating a fully functional API client module.

Key Features:
- Transforms parsed API structure into template-ready context data
- Analyzes endpoint descriptions to detect complex parameter requirements
- Extracts and processes path parameters from URI patterns
- Generates Pythonic method and class names following naming conventions
- Renders complete API client code using Jinja2 templates
- Creates production-ready okdesk_api_client.py module

The generated client provides:
- Structured class hierarchy matching API sections
- Error handling for API responses
- Full coverage of all documented endpoints

Use:
    python okdesk_client_generator.py
    or
    from okdesk_client_generator import create_okdesk_api_client
    create_okdesk_api_client("https://apidocs.okdesk.com/apidoc")

Output:
    okdesk_api_client.py - ready-to-use client for Okdesk API
"""

import jinja2

from api_parser import (
    ApiStructure,
    DescriptionElement,
    EndpointData,
    ParseResult,
    SectionData,
    parse_the_okdesk_api_documentation_site,
)


TEMPLATE_FILE = "template.jinja"
OUTPUT_FILE = "okdesk_api_client.py"


def _analyze_endpoint_description(
    desc: tuple[DescriptionElement, ...],
) -> tuple[str, bool]:
    """Analyze endpoint desc elements to extract metadata for code generation.

    Currently implements minimal functionality to detect table elements in the
    description. The function will be extended in the future to process and
    compile the actual description text from site.

    This preliminary implementation serves as a foundation for:
    - Detecting complex parameter structures (via table presence)
    - Preparing for comprehensive description text generation
    - Providing data for method signature generation

    Args:
        desc: Tuple of description elements from API documentation including
              paragraphs, headers, notes, and tables that describe the
              endpoint functionality and parameters.

    Returns:
        tuple: (str, bool)
            - str: Placeholder for future processed description text
                   (currently empty string)
            - bool: True if the description contains one or more table elements,
                    indicating complex parameter structures that may require
                    additional parameters in the generated method

    Note:
        This is a temporary implementation. Future versions will process:
        - Paragraph text for method documentation
        - Header hierarchies for section organization
        - Note elements for important warnings and context
        - Table data for parameter documentation

    Example:
        >>> elements = (
        ...     DescriptionElement(
        ...         'p', 'Search companies by various parameters'
        ...     ),
        ...     DescriptionElement(
        ...         'table', (('Param', 'Type'), ('name', 'string'))
        ...     )
        ... )
        >>> _analyze_endpoint_description(elements)
        ('', True)
    """
    table_in_desc: bool = False
    description: str = ""
    for item in desc:
        if item[0] == "table":
            table_in_desc = True
    return (description, table_in_desc)


def _get_path_params_string(uri: str) -> str:
    """
    Extract path parameters from URI and format them as method params string.

    Processes a URI string from API documentation to identify and extract path parameters
    (parameters enclosed in curly braces), excluding the API token parameter and its
    associated query parameters. Returns a comma-separated string suitable for use
    in Python method signatures.

    The function specifically:
    - Identifies parameters within curly braces {parameter}
    - Excludes the {?api_token} parameter and any query parameters
    - Returns parameters in the format ", param1, param2, ..."
    - Returns empty string if no path parameters are found

    Args:
        uri: The URI string from API documentation containing path parameters
             (e.g., "/api/v1/companies/{company_id}{?api_token}")

    Returns:
        str: A comma-separated string of path parameters prefixed with
            a comma, or empty string if no path parameters found.

    Examples:
        >>> _get_path_params_string("/api/v1/agreements/{id}{?api_token}")
        ", id"

        >>> _get_path_params_string("/api/v1/companies/{?api_token}")
        ""

    Notes:
        - Only extracts path parameters (before {?api_token})
        - Excludes all query parameters including {?api_token} and any
            following parameters
        - Uses recursive parsing to handle multiple parameters in complex URIs
        - Designed specifically for Okdesk API URI patterns
    """

    def _extract_path_parameters(text: str, args_list: list[str]) -> None:
        pos_open_brace = text.find("{")
        if pos_open_brace == -1:
            return
        pos_close_brace = text.find("}", pos_open_brace)
        if text[pos_open_brace : pos_open_brace + 11] == "{?api_token":
            return
        args_list.append(text[pos_open_brace + 1 : pos_close_brace])
        return _extract_path_parameters(text[pos_close_brace + 1 :], args_list)

    args_list: list[str] = []
    string_of_args: str = ""
    _extract_path_parameters(uri, args_list)
    for arg in args_list:
        string_of_args += f", {arg}"
    return string_of_args


def _extract_endpoint_path(uri: str) -> str:
    """
    Extract the clean endpoint path from a URI by removing query parameters.

    Processes URI strings from API documentation to isolate the actual
    endpoint path by stripping away the API token and any associated query
    parameters that follow the "{?api_token" pattern. This function is
    essential for generating clean endpoint paths for API client method
    implementations.

    Args:
        uri: The complete URI string from <code class="uri"> element
            containing both the endpoint path and query parameters.

    Returns:
        str: The clean endpoint path without query parameters, ready for use
            in API client method implementations.

    Examples:
        >>> _extract_endpoint_path("/api/v1/employees/groups{?api_token}")
        "/api/v1/employees/groups"

        >>> _extract_endpoint_path("/api/v1/users/sign_in")
        "/api/v1/users/sign_in"

        >>> _extract_endpoint_path("/api/v1/companies/{?api_token,name,id}")
        "/api/v1/companies/"

        >>> _extract_endpoint_path("/api/v1/issues/{issue_id}{?api_token}")
        "/api/v1/issues/{issue_id}"
    """
    api_token_pos = uri.find("{?api_token")
    if api_token_pos == -1:
        return uri
    return uri[:api_token_pos]


def _prepare_endpoints_template_context(
    endpoints: tuple[EndpointData, ...],
) -> list[dict[str, str]]:
    """
    Transform endpoint data into template context for API client code gen.

    Processes a collection of API endpoint definitions and converts them into
    a structured format suitable for Jinja2 template rendering. This function
    serves as a bridge between parsed documentation data and code generation
    by preparing all necessary context variables for method implementation.

    The transformation includes:
    - Extracting and cleaning endpoint paths
    - Generating method signatures with appropriate parameters
    - Detecting complex parameter requirements through documentation analysis
    - Converting English names to Python-compatible method names
    - Preparing documentation metadata for method docstrings

    Template Context Variables:
        name: Human-readable endpoint name (used in method docstring)
        link_to_documentation: URL official documentation (method reference)
        http_method: HTTP verb(GET/POST/PATCH/DELETE) for request construction
        path: Clean endpoint path without query params (request URL component)
        params: Params indicator (", params" if additional params required)
        desc: Endpoint description text (method docstring content)
        method_args_string: Method signature parameters
            (path params + optional params dict)
        method_name: Python method name in snake_case (generated from EN name)

    Parameter Detection Logic:
        Additional query parameters beyond api_token are inferred from:
        - Presence of table elements in endpoint description (complex params)
        - URI containing "{?api_token," pattern (multiple documented params)
        - URI containing "&" symbol (query parameter combinations)

    Args:
        endpoints: Collection of endpoint metadata extracted from API documentation

    Returns:
        List of endpoint context dictionaries ready for template rendering,
        each containing all necessary data to generate a complete API method.
    """
    endpoints_context = []
    for endpoint_data in endpoints:
        endpoint_context = {}
        endpoint_context["name"] = endpoint_data.name
        link_to_doc = endpoint_data.link_to_documentation
        endpoint_context["link_to_documentation"] = link_to_doc
        endpoint_context["http_method"] = endpoint_data.http_method
        endpoint_context["path"] = _extract_endpoint_path(endpoint_data.uri)
        endpoint_context["params"] = ""
        method_args_string = _get_path_params_string(endpoint_data.uri)
        description_text, has_table = _analyze_endpoint_description(
            endpoint_data.description
        )
        endpoint_context["desc"] = description_text
        # Determine if method requires additional parameters
        requires_additional_params = (
            has_table
            or "{?api_token," in endpoint_data.uri
            or "&" in endpoint_data.uri
        )
        if requires_additional_params:
            method_args_string += ", params: dict = {}"
            endpoint_context["params"] = ", params"
        endpoint_context["method_args_string"] = method_args_string
        # Generate Python method name
        _, endpoint_context["method_name"] = _generate_class_and_method_names(
            endpoint_data.eng_name
        )
        endpoints_context.append(endpoint_context)
    return endpoints_context


def _generate_class_and_method_names(display_name: str) -> tuple[str, str]:
    """
    Convert a display name into CamelCase and snake_case naming conventions.

    Transforms a human-readable endpoint name into standardized naming formats
    suitable for code generation. This function serves as a key component in
    creating Pythonic identifiers from API documentation names by:

    1. Normalizing separators (hyphens and underscores to spaces)
    2. Filtering to alphabetic characters only
    3. Generating both CamelCase and snake_case variants

    The generated names follow Python naming conventions:
    - CamelCase: For class names (PascalCase style)
    - snake_case: For method and attribute names

    Args:
        display_name: Human-readable name from API documentation
            (e.g., "Company search")

    Returns:
        tuple[str, str]:
            - CamelCase version suitable for class names
            - snake_case version suitable for methods and attributes

    Examples:
        >>> _generate_class_and_method_names("Company search")
        ("CompanySearch", "company_search")

    Note:
        This function intentionally preserves only alphabetic characters,
        removing any numbers, symbols, or punctuation that might be present
        in the original display name. All output is English-alphabet based.
    """
    # Normalize separators to spaces and convert to lower case
    norm_text = display_name.replace("-", " ").replace("_", " ")
    title_case_text = "".join(
        [char for char in norm_text.lower() if char.isalpha() or char == " "]
    )
    # Generate naming conventions
    camel_case_name = title_case_text.title().replace(" ", "")
    snake_case_name = title_case_text.replace(" ", "_")
    return (camel_case_name, snake_case_name)


def _prepare_section_template_context(
    section: SectionData,
) -> dict[str, str | list[dict[str, str]]]:
    """
    Transform section data into template context for API client class gen.

    Processes a documentation section containing related API endpoints and
    converts it into a structured format suitable for Jinja2 template
    rendering. This function prepares the complete context needed to generate
    a Python class that represents a logical API section with all its
    associated endpoints.

    The transformation includes:
    - Converting English section names to Python class naming conventions
    - Generating appropriate attribute names for the main API aggregator
    - Processing all endpoints within the section for method generation
    - Preparing section metadata for class-level documentation

    Template Context Structure:
        name: Human-readable section name (used in class docstring)
        class_name: PascalCase class name (generated from EN section name)
        aggregator_attr_name: snake_case attribute name for section class
            aggregator
        endpoints: List of endpoint context dictionaries for method generation

    Args:
        section: section metadata, containing the name, English name,
            and section endpoint metadata

    Returns:
        Dictionary containing complete template context for generating a
        Python class that represents the API section, including:
        - Section metadata for documentation
        - Class naming information
        - Processed endpoints data for methods implementation

    Note:
        This function works in conjunction with
        _prepare_endpoints_template_context to create a hierarchical template
        structure where sections become classes and endpoints become methods.
    """
    section_context = {}
    section_context["name"] = section.name
    class_name, aggregator_attr_name = _generate_class_and_method_names(
        section.eng_name
    )
    section_context["class_name"] = class_name
    section_context["aggregator_attr_name"] = aggregator_attr_name
    section_context["endpoints"] = _prepare_endpoints_template_context(
        section.endpoints
    )
    return section_context


def _prepare_root_template_context(
    api_structure: ApiStructure,
) -> dict[str, str | list[dict]]:
    """
    Prepare the root template context for gen the complete API client module.

    Transforms the top-level API documentation data structure into a complete
    context dictionary suitable for rendering API-client code using a Jinja2
    template. This function serves as the entry point for template data
    preparation, orchestrating the processing of all API sections and
    preparing the foundational data needed for client code generation.

    Template Context Structure:
        base_url: Normalized API base URL
        sections: List of section context dictionaries

    Arguments:
    api_structure: The complete parsed structure of the API documentation,
        containing the base URL and descriptions of all API sections.

    Returns:
        Dictionary containing the complete template context for generating
        the Python API client module, including:
        - Base URL for API requests
        - Hierarchical section and endpoint data for class and method gen
    """
    normalized_base_url = api_structure.base_url.replace("<", "{")
    normalized_base_url = normalized_base_url.replace(">", "}")
    sections_context = []
    for section in api_structure.sections:
        sections_context.append(_prepare_section_template_context(section))
    return {"sections": sections_context, "base_url": normalized_base_url}


def create_okdesk_api_client(url: str | None = None) -> None:
    """Main function to create Okdesk API client from documentation.

    This function orchestrates the complete client generation process:
    1. Parses API documentation from the specified URL
    2. Processes the data for template rendering
    3. Generates Python client code using Jinja2 template
    4. Handles errors and displays appropriate messages

    Args:
        url: URL of Okdesk API documentation site. If None, uses default
            English documentation.

    Output:
        Generates 'okdesk_api_client.py' file with complete API client
        implementation.

    Raises:
        Prints error messages to console if parsing or generation fails.
    """
    print("Parsing the Okdesk API documentation")
    if url is None:
        parse_result: ParseResult = parse_the_okdesk_api_documentation_site()
    else:
        parse_result = parse_the_okdesk_api_documentation_site(url)
    if "error" in parse_result:
        error_data = parse_result["error"]
        print(error_data.error_text)
        print(error_data.traceback_text)
        return
    elif "data" in parse_result:
        try:
            content = _prepare_root_template_context(parse_result["data"])
            loader = jinja2.FileSystemLoader("")
            env = jinja2.Environment(
                loader=loader, trim_blocks=True, keep_trailing_newline=True
            )
            tpl = env.get_template(TEMPLATE_FILE)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as client_file:
                client_file.write(tpl.render(content))
            print(f"Successfully generated API client: {OUTPUT_FILE}")
        except Exception as e:
            print(f"Failed to generate API client: {str(e)}")


if __name__ == "__main__":
    create_okdesk_api_client()
