"""Okdesk API Documentation Parser

This module provides functional to parse the Okdesk API documentation website
and extract structured information about API sections, endpoints, methods,
URIs, and their descriptions. The parser converts HTML documentation into
strongly-typed Python data structures for further processing.

Key Features:
- Parses API documentation from https://apidocs.okdesk.com/apidoc
- Extracts endpoints with their HTTP methods, URIs, and documentation links
- Processes complex description elements (paragraphs, headers, notes, tables)
- Validates extracted data against expected patterns
- Returns structured data using NamedTuple for immutability and type safety

Use:
parse_api_doc_result = parse_the_okdesk_api_documentation_site(
    link to the website with documentation
)

link to the website with documentation - A link to the Okdesk API
documentation site in any language. The resulting structure will contain
information in the same language (section names, endpoints, descriptions,
etc.). Optional.
"""

import re
import traceback
from typing import Iterator, Literal, NamedTuple, NotRequired, TypedDict
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import PageElement, ResultSet, Tag

DEFAULT_API_DOCS_URL = "https://apidocs.okdesk.com/apidoc"
TIMEOUT: int = 10
pattern_for_check_uri = re.compile(
    r"""(?x)
    /api/v1/                      # beginning of uri.
    [a-z]{2,}                     # first segment (min 2 letters).
    (?:_[a-z]{2,})?               # optional. The second part of the
                                  # first segment is separated by "_".
    (?:                           # additional segments.
        /                         # separator "/".
        (?:                       # options: regular segment - 1 or 2 words
        [a-z]{2,}(?:_[a-z]{2,})?  # separated by "_", at least two letters,
        |                         # or
        \{                        # braceted segment - 1 or more words
        [a-z]{2,}(?:_[a-z]{2,})*  # separated by "_", at least two letters,
        \}                        # enclosed in "{}".
        )                         #
    )*                            # 0 or more times.
    /?                            # optional "/" before token.
    \{\?api_token                 # required parameter: api_token.
    (?:                           # optional parameters.
        ,                         # through ","
        [a-z]{2,}                 # one or more words separated by "_",
        (?:_[a-z0-9]{2,})*        # possibly including numbers after the "_",
    )*                            # 0 or more times.
    \}                            # closing "}" for the token.
    (?:                           # optional query parameters.
        &                         # separator "&".
        (?P<param>                # parameter name
            [a-z]{2,}             # 1 or 2 words,
            (?:_[a-z]{2,})?       # separated by "_", at least two letters
        )                         #
        =                         # =
        \{(?P=param)\}            # the same parameter name in brace
    )*                            # 0 or more times.
    """
)


class DescriptionElement(NamedTuple):
    """Represents a single element in an endpoint description.

    Description elements can be paragraphs, headers, notes, or tables,
    each with their specific data structure and content type.

    Attributes:
        type: The type of description element ('p', 'h4', 'note', 'table')
        value: The content of the element, which varies by type:
            - str for paragraphs and headers
            - tuple[str, ...] for notes (multiple text lines)
            - tuple[tuple[str, ...], ...] for tables (rows and cells)
    """

    type: Literal["p", "h4", "note", "table"]
    value: str | tuple[str, ...] | tuple[tuple[str, ...], ...]


class EndpointData(NamedTuple):
    """Complete data structure for an API endpoint.

    Contains all metadata and documentation for a single API endpoint
    including its name, HTTP method, URI, documentation link, and detailed
    description.

    Attributes:
        name: Human-readable name of the endpoint (e.g., "Company search")
        link_to_documentation: Direct URL to the documentation
            for this endpoint
        method: HTTP method (GET, POST, PATCH, DELETE)
        uri: API endpoint URI with parameters
            (e.g., "/api/v1/companies/{company_id}{?api_token}")
        description: Structured description containing
            various content elements
    """

    name: str
    link_to_documentation: str
    method: str
    uri: str
    description: tuple[DescriptionElement, ...]


class SectionData(NamedTuple):
    """Represents a logical grouping of related API endpoints.

    API documentation is organized into sections (e.g., "Companies",
    "Tickets"), each containing multiple endpoints that share a common domain
    or functionality.

    Attributes:
        name: The section name (e.g., "Ticket management")
        endpoints: All API endpoints belonging to this section
    """

    name: str
    endpoints: tuple[EndpointData, ...]


class ApiStructure(NamedTuple):
    """Top-level container for the complete parsed API documentation.

    Represents the entire API structure with all sections and endpoints,
    along with the base URL for API calls.

    Attributes:
        base_url: The base URL for all API endpoints
            (e.g., "https://app.okdesk.ru")
        sections: All sections of the API documentation
    """

    base_url: str
    sections: tuple[SectionData, ...]


class ParseResult(TypedDict):
    """Result container for API parsing operations.

    Used to standardize success/error responses from parsing functions.

    Attributes:
        data: The successfully parsed API structure (present on success)
        error: Error message describing what went wrong (present on failure)
        traceback: Detailed technical error information (present on failure)
    """

    data: NotRequired[ApiStructure]
    error: NotRequired[str]
    traceback: NotRequired[str]


def ensure_tag(element: PageElement | None) -> Tag:
    """Ensure the BeautifulSoup element is a Tag instance.

    This type guard function provides runtime type safety when working with
    BeautifulSoup elements, ensuring we're working with proper HTML tags
    rather than other page elements like strings or comments.

    Args:
        element: BeautifulSoup page element, potentially None or non-Tag

    Returns:
        Tag: Guaranteed Tag instance

    Raises:
        TypeError: If element is not a Tag instance
    """
    if not isinstance(element, Tag):
        raise TypeError(f"Expected Tag, got {type(element)}")
    return element


def get_tags_only(elements: ResultSet | Iterator[PageElement]) -> list[Tag]:
    """Filter sequence to include only Tag elements.

    BeautifulSoup operations often return mixed content including strings
    and other element types. This function filters out non-Tag elements
    to work exclusively with proper HTML tags.

    Args:
        elements: Sequence of BeautifulSoup page elements

    Returns:
        list[Tag]: List containing only Tag instances
    """
    return [tag for tag in elements if isinstance(tag, Tag)]


def normalize_text(text: str) -> str:
    """Normalize text by removing extra whitespace and special characters.

    Cleans text extracted from HTML elements by:
    - Removing paragraph markers (¶) used in documentation
    - Collapsing multiple whitespace characters into single spaces
    - Trimming leading and trailing whitespace

    Args:
        text: Raw text string from HTML element

    Returns:
        str: Cleaned and normalized text
    """
    return " ".join(text.replace("¶", "").split())


def _parse_note(note: Tag) -> DescriptionElement:
    """Parse a note element from the documentation.

    Note elements are special div elements with class "note" that contain
    important information, warnings, or additional context about API usage.

    Args:
        note: BeautifulSoup Tag of a note element (div with class "note")

    Returns:
        DescriptionElement: Structured note data with type "note"
    """
    texts = (normalize_text(element.text) for element in note.children)
    non_empty_texts = tuple(text for text in texts if text.strip())
    return DescriptionElement("note", non_empty_texts)


def _parse_table(table: Tag) -> DescriptionElement:
    """Parse HTML table into structured table data.

    Converts HTML table elements into a two-dimensional tuple structure
    representing rows and cells. Processes both header (th) and data (td)
    cells.

    Args:
        table: BeautifulSoup Tag of a table element

    Returns:
        DescriptionElement: Structured table data with type "table"
    """
    table_data: list[tuple[str, ...]] = []
    table_rows = table.find_all("tr")
    for row in get_tags_only(table_rows):
        cells = row.find_all(["td", "th"])
        row_data = tuple(normalize_text(cell.text) for cell in cells)
        table_data.append(row_data)
    return DescriptionElement("table", tuple(table_data))


def _parse_description(elements: list[Tag]) -> tuple[DescriptionElement, ...]:
    """Parse endpoint description elements until URI examples section.

    Processes various HTML elements in endpoint documentation in sequence,
    stopping when encountering the URI examples section. Handles paragraphs,
    headers, tables, and note elements, converting them to structured data.

    Args:
        elements: List of HTML elements from endpoint documentation

    Returns:
        tuple[DescriptionElement, ...]: Structured description elements
    """
    description: list[DescriptionElement] = []
    for element in elements:
        if element.name == "p":
            description.append(
                DescriptionElement("p", normalize_text(element.text))
            )
        elif element.name == "h4" and "URI" in element.text:
            break
        elif element.name == "h4":
            description.append(
                DescriptionElement("h4", normalize_text(element.text))
            )
        elif element.name == "table":
            description.append(_parse_table(element))
        elif "note" in element.attrs.get("class", ""):
            description.append(_parse_note(element))
    return tuple(description)


def _validate_name(element_name: str) -> bool:
    """Validate section or endpoint name format.

    Checks if the name complies with the rules:
    - Must start with capital letter
    - Contains no more than one hyphen
    - Must not contain special characters
      except for one pair of specific quotation marks

    Args:
        element_name: Name to validate (section or endpoint name)

    Returns:
        bool: True if name matches expected pattern
    """
    if not element_name[0].isupper():
        return False
    element_name = element_name.replace("“", "", 1).replace("”", "", 1)
    element_name = element_name.replace("-", " ", 1).replace(" ", "")
    if not element_name.isalpha():
        return False
    return True


def _validate_endpoint_uri(uri: str) -> bool:
    """Validates an endpoint URI pattern.

    Verifies that the URI matches these rules:
    - Starts with /api/v1/
    - Path segments: English words (minimum 2 letters) or words separated by _
    - Optional segments (regular or in {})
    - Optional / before the token
    - Mandatory {?api_token
    - Optional parameters separated by commas
    - Mandatory closing }
    - Optional query parameters in the format &param={param}
    - Special case for the "/api/v1/users/sign_in" endpoint,
        as it does not require a token.

    Arguments:
    uri: The endpoint URI to validate

    Returns:
    bool: True if the URI matches the expected pattern
    """
    # Unique endpoint as it does not require an API token
    if uri == "/api/v1/users/sign_in":
        return True
    return bool(pattern_for_check_uri.fullmatch(uri))


def _validate_endpoint_metadata(name: str, http_method: str, uri: str) -> None:
    """Validate endpoint metadata.

    Performs comprehensive validation of endpoint name, HTTP method, and URI.

    Args:
        name: Endpoint name to validate
        http_method: HTTP method to validate
        uri: Endpoint URI to validate

    Raises:
        ValueError: If any validation check fails
    """
    valid_method = ("GET", "POST", "PATCH", "DELETE")
    if not _validate_name(name):
        raise ValueError(
            f'The received endpoint name does not match the pattern - "{name}"'
        )
    if http_method not in valid_method:
        raise ValueError(
            f'Invalid HTTP method value - "{http_method}". '
            f"One of them is expected: {valid_method}."
        )
    if not _validate_endpoint_uri(uri):
        raise ValueError(
            f'The obtained endpoint uri does not match the pattern - "{uri}"'
        )


def _extract_endpoint_metadata(
    endpoint_header_elements: list[Tag],
) -> tuple[str, str, str]:
    """Extract endpoint name, HTTP method, and URI from HTML elements.

    Parses the header section of an endpoint element to extract the three
    core metadata components: endpoint name, HTTP method, and URI.

    Args:
        endpoint_header_elements: First two child elements of endpoint
            container

    Returns:
        tuple[str, str, str]: (endpoint_name, http_method, uri)

    Raises:
        ValueError: If header structure doesn't contain expected elements
    """
    acount_name, action_heading = endpoint_header_elements
    action_heading_children = get_tags_only(action_heading.children)
    if len(action_heading_children) < 2:
        raise ValueError('"action-heading" doesn\'t contain method and URI')
    endpoint_name = acount_name.text
    http_method = action_heading_children[0].text
    endpoint_uri = action_heading_children[1].text
    _validate_endpoint_metadata(endpoint_name, http_method, endpoint_uri)
    return (
        endpoint_name,
        http_method,
        endpoint_uri,
    )


def _validate_endpoint_children(
    endpoint: Tag, endpoint_children: list[Tag]
) -> None:
    """Validate the structure of endpoint child elements.

    Ensures that an endpoint element contains the minimum required number
    of child elements (at least 3) for proper parsing. This includes:
    - Endpoint name element
    - Action heading with method and URI
    - Description content

    Args:
        endpoint: BeautifulSoup Tag of the endpoint element
        endpoint_children: List of child Tag elements from the endpoint

    Raises:
        ValueError: If endpoint has fewer than 3 child elements, indicating
                   incomplete or malformed endpoint structure
    """
    if len(endpoint_children) < 3:
        endpoint_id = endpoint.get("id", "unknown")
        value_error_text = (
            f'Endpoint "{endpoint_id}" has only {len(endpoint_children)} '
            "children, expected at least 3"
        )
        raise ValueError(value_error_text)


def _parse_endpoint(endpoint: Tag, base_url: str) -> EndpointData:
    """Parse complete endpoint element into structured data.

    Processes a full endpoint definition including:
    - Structural validation of child elements
    - Metadata extraction (name, HTTP method, URI)
    - Documentation link generation
    - Description parsing and normalization

    Args:
        endpoint: BeautifulSoup Tag of an endpoint -- "action"-class div
        base_url: Base URL for documentation link generation

    Returns:
        EndpointData: Complete structured endpoint data
    """
    endpoint_children: list[Tag] = get_tags_only(endpoint.children)
    _validate_endpoint_children(endpoint, endpoint_children)
    ep_name, ep_http_method, ep_uri = _extract_endpoint_metadata(
        endpoint_children[:2]
    )
    endpoint_doc_link = urljoin(base_url, f"#!{endpoint.get('id', '')}")
    return EndpointData(
        ep_name,
        endpoint_doc_link,
        ep_http_method,
        ep_uri,
        _parse_description(endpoint_children[2:]),
    )


def _extract_section_name(section_element: Tag) -> str:
    """Extract and normalize section name from HTML element.

    Finds the section heading element and returns its normalized text content.

    Args:
        section_element: BeautifulSoup Tag of a section element

    Returns:
        str: Normalized section name

    Raises:
        ValueError: If section name validation fails
    """
    section_group_heading = ensure_tag(
        section_element.find(class_="group-heading")
    )
    section_name = normalize_text(section_group_heading.text)
    if _validate_name(section_name):
        return section_name
    else:
        value_error_text = (
            "The received section name does not match the pattern - "
            f'"{section_name}"'
        )
        raise ValueError(value_error_text)


def _parse_section(section_element: Tag, base_url: str) -> SectionData:
    """Parse complete documentation section with all endpoints.

    Processes a section element to extract its name and parse all contained
    endpoints, returning a complete section data structure.

    Args:
        section_element: BeautifulSoup Tag of a section element
        base_url: Base URL for endpoint documentation links

    Returns:
        SectionData: Complete structured section data
    """
    endpoints_data: list[EndpointData] = []
    section_name = _extract_section_name(section_element)
    endpoints = get_tags_only(section_element.find_all(class_="action"))
    for endpoint in endpoints:
        endpoints_data.append(_parse_endpoint(endpoint, base_url))
    return SectionData(section_name, tuple(endpoints_data))


def _extract_api_base_url(content: Tag) -> str:
    """
    Extract API base URL from documentation content.

    Finds the hostname element in the documentation that specifies
    the base URL for all API endpoints.

    Args:
        content: BeautifulSoup Tag of the main content div

    Returns:
        str: API base URL (e.g., "https://app.okdesk.ru")
    """
    hostname = ensure_tag(content.find("span", class_="hostname"))
    return hostname.text


def _parse_content_okdesk_api_doc_site(
    base_url: str, content: Tag
) -> ApiStructure:
    """Parse complete Okdesk API documentation structure.

    Processes the main content area to extract all sections and build
    the complete API documentation hierarchy with base URL.

    Args:
        base_url: Base URL of the documentation site
        content: BeautifulSoup Tag of the main content div

    Returns:
        ApiStructure: Complete parsed API documentation structure
    """
    api_data: list[SectionData] = []
    api_base_url = _extract_api_base_url(content)
    sections = get_tags_only(content.find_all("section"))
    for section in sections:
        api_data.append(_parse_section(section, base_url))
    return ApiStructure(api_base_url, tuple(api_data))


def get_site_base_url(url: str) -> str:
    """Extract base URL by removing URL fragment identifiers.

    Uses urldefrag to remove any fragment identifiers from the URL
    while preserving the base URL for documentation parsing.

    Args:
        url: Full URL possibly containing fragments

    Returns:
        str: Base URL without fragments
    """
    defrag_url = urldefrag(url)
    return defrag_url.url


def _create_error_result(error_message: str) -> ParseResult:
    """
    Create standardized error result structure.

    Generates a consistent error response format including both
    user-friendly error message and technical traceback for debugging.

    Args:
        error_message: Descriptive error message for users

    Returns:
        ParseResult: Structured error response
    """
    return {"error": error_message, "traceback": traceback.format_exc()}


def parse_the_okdesk_api_documentation_site(
    api_docs_url: str = DEFAULT_API_DOCS_URL,
) -> ParseResult:
    """Main function to parse Okdesk API documentation.

    Orchestrates the complete parsing workflow:
    1. Fetches documentation HTML from specified URL
    2. Parses content with BeautifulSoup
    3. Extracts structured API data with validation
    4. Handles errors gracefully with reporting

    Args:
        api_docs_url: URL of Okdesk API documentation site

    Returns:
        ParseResult: Success with parsed data or error information
    """
    base_url = get_site_base_url(api_docs_url)
    try:
        with requests.Session() as session:
            okdesk_api_doc_site = session.get(base_url, timeout=TIMEOUT)
        okdesk_api_doc_site.raise_for_status()
        soup = BeautifulSoup(okdesk_api_doc_site.text, "html.parser")
        content = ensure_tag(soup.find(class_="content"))
        api_data = _parse_content_okdesk_api_doc_site(base_url, content)
    except requests.Timeout:
        return _create_error_result("Request timeout")
    except requests.ConnectionError:
        return _create_error_result("Connection error")
    except requests.HTTPError as e:
        return _create_error_result(f"HTTP error: {e.response.status_code}")
    except (AttributeError, TypeError, ValueError) as e:
        return _create_error_result(f"Parsing error: {str(e)}")
    except Exception as e:
        return _create_error_result(f"Unexpected error: {str(e)}")
    return {"data": api_data}
