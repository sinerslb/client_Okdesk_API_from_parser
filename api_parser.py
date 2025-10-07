import json
import traceback
from typing import Iterator, NotRequired, TypeAlias, TypedDict
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import PageElement, ResultSet, Tag

Paragraph_or_note: TypeAlias = tuple[str, ...]
Table_element: TypeAlias = tuple[str, list[list[str]]]
Description: TypeAlias = list[Table_element | Paragraph_or_note]
EndpointData = TypedDict(
    "EndpointData",
    {
        "endpoint_link": str,
        "method": str,
        "uri": str,
        "description": Description,
    },
)
ApiStructure: TypeAlias = dict[str, dict[str, EndpointData]]
ParseResult = TypedDict(
    "ParseResult",
    {
        "data": NotRequired[ApiStructure],
        "error": NotRequired[str],
        "traceback": NotRequired[str],
    },
)


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


def _parse_note(note: Tag) -> Paragraph_or_note:
    """Parsing note element.

    Args:
        note (Tag): "note"-class div HTML element

    Returns:
        Paragraph_or_note: a tuple with the element type "note" specified at
            the zero position, and the note data
    """
    texts = (normalize_text(element.text) for element in note.children)
    non_empty_texts = (text for text in texts if text.strip())
    return ("note", *non_empty_texts)


def _parse_table(table: Tag) -> Table_element:
    """Parsing table HTML element.

    Args:
        table (Tag): <table> HTML element

    Returns:
        Table_element: a tuple with the element type "table" specified at
            the zero position, and the table data
    """
    table_data: list[list[str]] = []
    table_rows = table.find_all("tr")
    for row in get_tags_only(table_rows):
        cells = row.find_all(["td", "th"])
        row_data = [normalize_text(cell.text) for cell in cells]
        table_data.append(row_data)
    return ("table", table_data)


def _parse_description(elements: list[Tag]) -> Description:
    """Parse endpoint description elements until URI example section.

    Processes 'p', 'h4', 'table', and 'note' elements, stopping when
    encountering an 'h4' element containing 'URI' text.

    Args:
        ep_children (list[Tag]): list of HTML elements
            from endpoint documentation

    Returns:
        Description: structured description containing text,
            headers, tables, and notes
    """
    description: Description = []
    for element in elements:
        if element.name == "p":
            description.append(("p", normalize_text(element.text)))
        elif element.name == "h4" and "URI" in element.text:
            break
        elif element.name == "h4":
            description.append(("h4", normalize_text(element.text)))
        elif element.name == "table":
            description.append(_parse_table(element))
        elif "note" in element.attrs.get("class", ""):
            description.append(_parse_note(element))
    return description


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


def _parse_endpoint(
    endpoint: Tag, endpoint_links: dict, section_name: str
) -> tuple[str, EndpointData]:
    """Parse individual endpoint element into structured data.

    Args:
        endpoint (Tag): "action"-class div HTML element
        endpoint_links (dict): Dictionary mapping endpoint names
            to documentation URLs
        section_name (str): name of the parent section

    Returns:
        tuple[str, EndpointData]: endpoint name and endpoint data
            (description, list of parameters, etc)

    Raises:
        ValueError: if an endpoint has fewer than three child elements
    """
    endpoint_children: list[Tag] = get_tags_only(endpoint.children)
    if len(endpoint_children) < 3:
        raise ValueError("Not enough elements to parse endpoint")
    ep_name, ep_http_method, ep_uri = _extract_endpoint_metadata(
        endpoint_children[:2]
    )
    endpoint_link = endpoint_links[section_name][ep_name]
    endpoint_data: EndpointData = {
        "endpoint_link": endpoint_link,
        "method": ep_http_method,
        "uri": ep_uri,
        "description": _parse_description(endpoint_children[2:]),
    }
    return (ep_name, endpoint_data)


def _get_section_name(section_element: Tag) -> str:
    """Return name of the section.

    Args:
        section_element (Tag): "section" HTML element
    """
    section_group_heading = ensure_tag(
        section_element.find(class_="group-heading")
    )
    return normalize_text(section_group_heading.text)


def _parse_section(
    section_element: Tag, endpoint_links: dict
) -> tuple[str, dict[str, EndpointData]]:
    """Parsing the section HTML element.

    Args:
        section_element (Tag): "section" HTML element
        endpoint_links (dict): links to endpoint documentation,
            divided into sections

    Returns:
        tuple[str, dict[str, EndpointData]]: the section name and
            information about all section endpoints
    """
    section_data: dict[str, EndpointData] = {}
    section_name = _get_section_name(section_element)
    endpoints = get_tags_only(section_element.find_all(class_="action"))
    for endpoint in endpoints:
        endpoint_name, endpoint_data = _parse_endpoint(
            endpoint, endpoint_links, section_name
        )
        section_data[endpoint_name] = endpoint_data
    return (section_name, section_data)


def _get_okdesk_api_data(content: Tag, endpoint_links: dict) -> ApiStructure:
    """Return parsed Okdesk API data.

    Args:
        content (Tag): "content"-class div HTML element
        endpoint_links (dict): dictionary of endpoint documentation links

    Returns:
        ApiStructure: structured information about API resources
            divided into sections
    """
    api_data: ApiStructure = {}
    sections = get_tags_only(content.find_all("section"))
    for section in sections:
        section_name, section_data = _parse_section(section, endpoint_links)
        api_data[section_name] = section_data
    return api_data


def _parse_resource_group_data(group: Tag, base_url: str) -> dict[str, str]:
    """Parsing the resource-group element.

    Args:
        group (Tag): "resource-group"-class div HTML element
        base_url (str): The base URL of the Okdesk API documentation site

    Returns:
        dict[str, str]: {"endpoint name": "link to documentation"}
    """
    rg_r_a_links = get_tags_only(group.find_all(class_="rg-r-a-link"))
    list_of_endpoint_links_pair = [
        (rg_r_a_link.text, urljoin(base_url, str(rg_r_a_link["href"])))
        for rg_r_a_link in rg_r_a_links
    ]
    return dict(list_of_endpoint_links_pair)


def _parse_navigation_structure(
    nav: Tag, base_url: str
) -> dict[str, dict[str, str]]:
    """Parse navigation to get endpoint doc links grouped by sections.

    Args:
        nav (Tag): 'nav'  HTML element
        base_url (str): Base URL of Okdesk API documentation

    Returns:
        dict[str, dict[str, dict[str, str]]]: {
            "section name": {
                "endpoint name": "link to documentation"
            }
        }
    """
    sections_structure: dict[str, dict[str, str]] = {}
    resource_groups = get_tags_only(nav.find_all(class_="resource-group"))
    for group in resource_groups:
        rg_link = group.find(class_="rg-link")
        if rg_link is None:
            continue
        sections_structure[rg_link.text] = _parse_resource_group_data(
            group, base_url
        )
    return sections_structure


def get_base_url(url: str) -> str:
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
        dict: Okdesk API documentation data dictionary
            or error data dictionary
    """
    api_data = {}
    base_url = get_base_url(api_docs_url)
    try:
        with requests.Session() as session:
            okdesk_api_site = session.get(base_url)
        okdesk_api_site.raise_for_status()
        soup = BeautifulSoup(okdesk_api_site.text, "html.parser")
        nav = ensure_tag(soup.find("nav"))
        content = ensure_tag(soup.find(class_="content"))
        navigation_structure = _parse_navigation_structure(nav, base_url)
        api_data = _get_okdesk_api_data(content, navigation_structure)
    except requests.RequestException as e:
        return _create_error_result(f"Network error: {str(e)}")
    except (AttributeError, TypeError, ValueError) as e:
        return _create_error_result(f"Parsing error: {str(e)}")
    except Exception as e:
        return _create_error_result(f"Unexpected error: {str(e)}")
    return {"data": api_data}


if __name__ == "__main__":
    okdesk_api_data = get_parsed_api_data()
    if "traceback" in okdesk_api_data:
        print(okdesk_api_data["traceback"])
    else:
        with open("okdesk_api_data.json", "w", encoding="utf-8") as f:
            json.dump(okdesk_api_data, f, ensure_ascii=False, indent=4)
        print("Ready!")
