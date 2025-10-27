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
    table_in_desc: bool = False
    description: str = ""
    for item in desc:
        if item[0] == "table":
            table_in_desc = True
    return (description, table_in_desc)


def _get_path_params_string(uri: str) -> str:
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
    api_token_pos = uri.find("{?api_token")
    if api_token_pos == -1:
        return uri
    return uri[:api_token_pos]


def _prepare_endpoints_template_context(
    endpoints: tuple[EndpointData, ...],
) -> list[dict[str, str]]:
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
    normalized_base_url = api_structure.base_url.replace("<", "{")
    normalized_base_url = normalized_base_url.replace(">", "}")
    sections_context = []
    for section in api_structure.sections:
        sections_context.append(_prepare_section_template_context(section))
    return {"sections": sections_context, "base_url": normalized_base_url}


def create_okdesk_api_client(url: str | None = None) -> None:
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
