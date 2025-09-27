import json
import traceback
from typing import Iterator
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, ResultSet, Tag

Result_set = ResultSet[PageElement | Tag | NavigableString]


def get_one_element_class_tag(
        element: PageElement | None
) -> Tag:
    """Return element of class Tag.

    Args:
        element (PageElement | None): result Tag.find()

    Returns:
        Tag: The same element as in the input,
            but for mypy it already belongs to the Tag class

    The function is needed only to prevent type errors.
    The code can work without it, but mypy throws errors.
    Since the page being analyzed is already known,
    an exception will never be thrown.
    """
    if not isinstance(element, Tag):
        raise Exception
    return element


def get_elements_of_class_tag(
        elements: Result_set | Iterator[PageElement]
) -> list[Tag]:
    """Return all elements of class Tag from the given iterator.

    Args:
        elements (Result_set | Iterator[PageElement]): result Tag.find_all(),
            or Tag.children

    Returns:
        list[Tag]: The same elements as in the input data,
            but for mypy they already belong to the Tag class

    The function is needed only to prevent type errors.
    The code can work without it, but mypy throws errors.
    """
    return [
        tag for tag in elements if isinstance(tag, Tag)
    ]


def parse_a_section(
        section_element: Tag,
        dict_links_to_docs: dict
) -> dict[str, dict[str, str | list[list[str | list[str]]]]]:
    """Parses section.

    Args:
        section_element (Tag): web element 'section'
        section_data (dict[str, dict[str, str]]): dictionary with sections data
    """
    section_data: dict[str, dict[str, str | list[list[str | list[str]]]]] = {}
    resources = get_elements_of_class_tag(
        section_element.find_all(class_='resource')
    )
    section_h2 = get_one_element_class_tag(
        section_element.find('h2')
    )
    section_name = section_h2.text.replace(' ¶', '')
    for resource in resources:
        endpoints = get_elements_of_class_tag(resource.children)
        for endpoint in endpoints:
            ep_children: list[Tag] = get_elements_of_class_tag(
                endpoint.children
            )
            endpoint_name = ep_children[0].text
            section_data[endpoint_name] = {}
            endpoint_data = section_data[endpoint_name]
            ep_url_data: list[Tag] = get_elements_of_class_tag(
                ep_children[1].children
            )
            link_to_doc = dict_links_to_docs[section_name][endpoint_name]
            endpoint_data['link_to_the_doc'] = link_to_doc
            endpoint_data['method'] = ep_url_data[0].text
            endpoint_data['uri'] = ep_url_data[1].text
            endpoint_data['description'] = []
    return section_data


def get_okdesk_api_data(
            content: Tag,
            dict_links_to_docs: dict
) -> dict[str, dict[str, dict[str, str | list[list[str | list[str]]]]]]:
    api_data = {}
    sections = get_elements_of_class_tag(
        content.find_all('section')
    )
    for section in sections:
        section_group_heading = get_one_element_class_tag(
            section.find(class_='group-heading')
        )
        section_name = section_group_heading.text.replace(' ¶', '')
        api_data[section_name] = parse_a_section(
            section,
            dict_links_to_docs
        )
    return api_data


def get_the_endpoint_structure_with_links_to_docs(
        nav: Tag,
        base_url: str
) -> dict[str, dict[str, dict[str, str]]]:
    """Return the documentation data structure and links to the site.

    Args:
        soup (BeautifulSoup): a Beautifulsoup object with the parsed Okdesk API
            documentation site
        base_url (str): Okdesk API documentation website base URL

    Returns:
        dict[str, dict[str, dict[str, str]]]: dictionary of API documentation
        sections, listing endpoints and links to descriptions of those
        endpoints
    """
    endpoint_structure = {}
    resource_groups = get_elements_of_class_tag(
        nav.find_all(
            class_='resource-group'
        )
    )
    for group in resource_groups:
        rg_link = group.find(
            class_='rg-link'
        )
        if rg_link is None:
            continue
        rg_r_a_links = get_elements_of_class_tag(
            group.find_all(
                class_='rg-r-a-link'
            )
        )
        endpoint_structure[rg_link.text] = dict(
            [
                (
                    rg_r_a_link.text,
                    urljoin(
                            base_url,
                            str(rg_r_a_link['href'])
                        )
                ) for rg_r_a_link in rg_r_a_links
            ]
        )
    return endpoint_structure


def get_base_url(
        url: str
) -> str:
    """Return base url.

    Args:
        url (str): website URL

    Returns:
        str: base website URL
    """
    defrag_url = urldefrag(url)
    return defrag_url.url


def get_parsed_api_data(
    api_docs_url: str = 'https://apidocs.okdesk.com/apidoc'
) -> dict:
    """Return parsed documentation data.

    Args:
        api_docs_url (str, optional): Link to documentation site Okdesk API.

    Returns:
        dict: Okdesk API documentation data dictionary
    """
    api_data = {}
    base_url = get_base_url(api_docs_url)
    try:
        with requests.Session() as session:
            okdesk_api_site = session.get(
                base_url
            )
        okdesk_api_site.raise_for_status()
        soup = BeautifulSoup(okdesk_api_site.text, 'html.parser')
        nav = get_one_element_class_tag(
            soup.find('nav')
        )
        content = get_one_element_class_tag(
            soup.find(class_='content')
        )
        api_structure = get_the_endpoint_structure_with_links_to_docs(
            nav,
            base_url
        )
        api_data = get_okdesk_api_data(
            content,
            api_structure
        )
    except Exception as ex:
        ex_traceback = traceback.format_exc()
        return {
            'error': str(ex),
            'traceback': ex_traceback
        }
    return api_data


if __name__ == '__main__':
    okdesk_api_data = get_parsed_api_data()
    with open('okdesk_api_data.json', 'w', encoding='utf-8') as f:
        json.dump(
            okdesk_api_data,
            f,
            ensure_ascii=False,
            indent=4
        )
    print('Ready!')
