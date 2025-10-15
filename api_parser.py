import traceback
from typing import Iterator, Literal, NamedTuple, NotRequired, TypedDict
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import PageElement, ResultSet, Tag


DEFAULT_API_DOCS_URL = "https://apidocs.okdesk.com/apidoc"
TIMEOUT: int = 10


class DescriptionElement(NamedTuple):
    type: Literal["p", "h4", "note", "table"]
    value: str | tuple[str, ...] | tuple[tuple[str, ...], ...]


class EndpointData(NamedTuple):
    name: str
    link_to_documentation: str
    method: str
    uri: str
    description: tuple[DescriptionElement, ...]


class SectionData(NamedTuple):
    name: str
    endpoints: tuple[EndpointData, ...]


class ApiStructure(NamedTuple):
    base_url: str
    sections: tuple[SectionData, ...]


class ParseResult(TypedDict):
    data: NotRequired[ApiStructure]
    error: NotRequired[str]
    traceback: NotRequired[str]


def ensure_tag(element: PageElement | None) -> Tag:
    """Ensure the element is a Tag instance or raise TypeError.

    Args:
        element(PageElement | None): Result of Tag.find()

    Returns:
        Tag: The input element guaranteed to be a Tag instance

    Raises:
        TypeError: If element is not a Tag
    """
    if not isinstance(element, Tag):
        raise TypeError(f"Expected Tag, got {type(element)}")
    return element


def get_tags_only(elements: ResultSet | Iterator[PageElement]) -> list[Tag]:
    """Return all HTML elements of type Tag from the given iterator.

    Args:
        elements (Result_set | Iterator[PageElement]): result Tag.find_all()
            or Tag.children

    Returns:
        list[Tag]: List of HTML elements of type Tag
    """
    return [tag for tag in elements if isinstance(tag, Tag)]


def normalize_text(text: str) -> str:
    """Clear a line of extra spaces, line breaks, and ¶.

    Args:
        string (str): string

    Returns:
        str: a string without spaces or line breaks
    """
    return " ".join(text.replace("¶", "").split())


def _parse_note(note: Tag) -> DescriptionElement:
    """Parsing note element.
    """
    texts = (normalize_text(element.text) for element in note.children)
    non_empty_texts = tuple(text for text in texts if text.strip())
    return DescriptionElement("note", non_empty_texts)


def _parse_table(table: Tag) -> DescriptionElement:
    """Parsing table HTML element.
    """
    table_data: list[tuple[str, ...]] = []
    table_rows = table.find_all("tr")
    for row in get_tags_only(table_rows):
        cells = row.find_all(["td", "th"])
        row_data = tuple(normalize_text(cell.text) for cell in cells)
        table_data.append(row_data)
    return DescriptionElement("table", tuple(table_data))


def _parse_description(elements: list[Tag]) -> tuple[DescriptionElement, ...]:
    """Parse endpoint description elements until URI example section.

    Processes 'p', 'h4', 'table', and 'note' elements, stopping when
    encountering an 'h4' element containing 'URI' text.
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


def _extract_endpoint_metadata(
    endpoint_children_slice: list[Tag],
) -> tuple[str, str, str]:
    """Extract endpoint name, HTTP method, and URI from endpoint children.

    Args:
        endpoint_children_slice (list[Tag]): a list of the first two child
            elements of a "action"-class div HTML element

    Returns:
        tuple[str, str, str]: (endpoint_name, http_method, uri)
    """
    acount_name, action_heading = endpoint_children_slice
    action_heading_children = get_tags_only(action_heading.children)
    return (
        acount_name.text,
        action_heading_children[0].text,
        action_heading_children[1].text,
    )


def _parse_endpoint(endpoint: Tag, base_url: str) -> EndpointData:
    """Parse individual endpoint element into structured data.

    Raises:
        ValueError: if an endpoint has fewer than three child elements
    """
    endpoint_children: list[Tag] = get_tags_only(endpoint.children)
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


def _get_section_name(section_element: Tag) -> str:
    """Return name of the section.

    Args:
        section_element (Tag): "section" HTML element
    """
    section_group_heading = ensure_tag(
        section_element.find(class_="group-heading")
    )
    return normalize_text(section_group_heading.text)


def _parse_section(section_element: Tag, base_url: str) -> SectionData:
    endpoints_data: list[EndpointData] = []
    section_name = _get_section_name(section_element)
    endpoints = get_tags_only(section_element.find_all(class_="action"))
    for endpoint in endpoints:
        endpoints_data.append(_parse_endpoint(endpoint, base_url))
    return SectionData(section_name, tuple(endpoints_data))


def _extract_api_base_url(content: Tag) -> str:
    hostname = ensure_tag(content.find("span", class_="hostname"))
    return hostname.text


def _parse_content_okdesk_api_doc_site(
    base_url: str, content: Tag
) -> ApiStructure:
    api_data: list[SectionData] = []
    api_base_url = _extract_api_base_url(content)
    sections = get_tags_only(content.find_all("section"))
    for section in sections:
        api_data.append(_parse_section(section, base_url))
    return ApiStructure(api_base_url, tuple(api_data))


def get_site_base_url(url: str) -> str:
    """Return base url.

    Args:
        url (str): website URL

    Returns:
        str: base website URL
    """
    defrag_url = urldefrag(url)
    return defrag_url.url


def _create_error_result(error_message: str) -> ParseResult:
    """Generates a structured error result."""
    return {"error": error_message, "traceback": traceback.format_exc()}


def get_parsed_api_data(
    api_docs_url: str = "https://apidocs.okdesk.com/apidoc",
) -> ParseResult:
    """Return parsed documentation data.

    Args:
        api_docs_url (str, optional): Link to documentation site Okdesk API.

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
