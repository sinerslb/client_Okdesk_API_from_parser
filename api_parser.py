import json
import requests
from urllib.parse import urldefrag


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