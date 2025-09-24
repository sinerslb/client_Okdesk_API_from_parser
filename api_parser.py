from bs4 import BeautifulSoup
import json
import requests
from urllib.parse import urldefrag, urljoin


def get_the_endpoint_structure_with_links_to_docs(
        soup: BeautifulSoup,
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
    resource_groups = soup.find_all(
        class_='resource-group'
    )
    for group in resource_groups:
        rg_link = group.find(
            class_='rg-link'
        )
        if rg_link is None:
            continue
        rg_r_a_links = group.find_all(
            class_='rg-r-a-link'
        )
        endpoint_structure[rg_link.text] = dict(
            [
                (
                    rg_r_a_link.text,
                    {
                        'link_to_the_manual': urljoin(
                            base_url,
                            rg_r_a_link['href']
                        )
                    }
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
        api_data = get_the_endpoint_structure_with_links_to_docs(
            soup,
            base_url
        )
    except Exception as ex:
        api_data['error'] = str(ex)
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