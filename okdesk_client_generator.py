import jinja2

from api_parser import (
    ApiStructure,
    DescriptionElement,
    EndpointData,
    ParseResult,
    SectionData,
    parse_the_okdesk_api_documentation_site,
)


def _create_description(
    desc: tuple[DescriptionElement, ...],
) -> tuple[str, bool]:
    table_in_desc: bool = False
    description: str = ""
    for item in desc:
        if item[0] == "table":
            table_in_desc = True
    return (description, table_in_desc)


def _get_string_of_args(uri: str) -> str:
    def _extract_args(text: str, args_list: list[str]) -> None:
        pos_open_brace = text.find("{")
        if pos_open_brace == -1:
            return
        pos_close_brace = text.find("}", pos_open_brace)
        if text[pos_open_brace:pos_open_brace + 11] == "{?api_token":
            return
        args_list.append(text[pos_open_brace + 1:pos_close_brace])
        return _extract_args(text[pos_close_brace + 1:], args_list)

    args_list: list[str] = []
    string_of_args: str = ""
    _extract_args(uri, args_list)
    for arg in args_list:
        string_of_args += f", {arg}"
    return string_of_args


def _get_uri_without_params(uri: str) -> str:
    api_token_pos = uri.find("{?api_token")
    if api_token_pos == -1:
        return uri
    return uri[:api_token_pos]


def _process_endpoints(endpoints: tuple[EndpointData, ...]) -> list[dict]:
    endpoints_info_for_content = []
    for endpoint_data in endpoints:
        endpoint_content = {}
        endpoint_content["name"] = endpoint_data.name
        endpoint_content["link_to_documentation"] = (
            endpoint_data.link_to_documentation
        )
        endpoint_content["http_method"] = endpoint_data.http_method
        endpoint_content["uri"] = _get_uri_without_params(endpoint_data.uri)
        endpoint_content["params"] = ""
        string_of_args = _get_string_of_args(endpoint_data.uri)
        desc, table_in_desc = _create_description(endpoint_data.description)
        endpoint_content["desc"] = desc
        needs_params = (
            table_in_desc
            or "{?api_token," in endpoint_data.uri
            or "&" in endpoint_data.uri
        )
        if needs_params:
            string_of_args += ", params: dict = {}"
            endpoint_content["params"] = ", params"
        endpoint_content["string_of_args"] = string_of_args
        _, endpoint_content["method_name"] = get_camel_and_snake_case_text(
            endpoint_data.eng_name
        )
        endpoints_info_for_content.append(endpoint_content)
    return endpoints_info_for_content


def get_camel_and_snake_case_text(eng_name: str) -> tuple[str, str]:
    eng_name = eng_name.replace("-", " ").replace("_", " ")
    eng_name = "".join(
        [char for char in eng_name.title() if char.isalpha() or char == " "]
    )
    camel_case_text = eng_name.replace(" ", "")
    snake_case_text = eng_name.lower().replace(" ", "_")
    return (camel_case_text, snake_case_text)


def _process_section(section: SectionData) -> dict:
    class_representing_a_section = {}
    class_representing_a_section["name"] = section.name
    class_name, agregator_attr_name = get_camel_and_snake_case_text(
        section.eng_name
    )
    endpoints = _process_endpoints(section.endpoints)
    class_representing_a_section["class_name"] = class_name
    class_representing_a_section["agregator_attr_name"] = agregator_attr_name
    class_representing_a_section["endpoints"] = endpoints
    return class_representing_a_section


def _get_content_for_render(data: ApiStructure) -> dict:
    base_url = data.base_url.replace("<", "{").replace(">", "}")
    sections = []
    for section in data.sections:
        sections.append(_process_section(section))
    return {"sections": sections, "base_url": base_url}


def create_okdesk_api_client(url: str | None = None) -> None:
    if url is None:
        parse_result: ParseResult = parse_the_okdesk_api_documentation_site()
    else:
        parse_result = parse_the_okdesk_api_documentation_site(url)
    if "error" in parse_result:
        error_data = parse_result["error"]
        print(error_data.error_text)
        print(error_data.traceback_text)
        return
    if "data" in parse_result:
        content = _get_content_for_render(parse_result["data"])
        loader = jinja2.FileSystemLoader("")
        env = jinja2.Environment(
            loader=loader, trim_blocks=True, keep_trailing_newline=True
        )
        tpl = env.get_template("template.jinja")
        with open(
            "okdesk_api_client.py", "w", encoding="utf-8"
        ) as client_file:
            client_file.write(tpl.render(content))


if __name__ == "__main__":
    create_okdesk_api_client()
