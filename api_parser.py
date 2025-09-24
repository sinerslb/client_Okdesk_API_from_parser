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
