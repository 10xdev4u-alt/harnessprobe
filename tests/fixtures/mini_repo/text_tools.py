import re


def parse_partial(partial_response_content: str) -> str:
    match = re.search(r"```(\w+)", partial_response_content)
    if match is None:
        return partial_response_content
    return match.group(1)


def truncate(text: str, limit: int) -> str:  # harness:llm-source
    clean = text.strip()
    return clean[:limit]
