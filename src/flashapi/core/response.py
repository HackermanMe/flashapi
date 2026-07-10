"""Response formatting."""

from typing import Callable


def default_formatter(data: list | dict, meta: dict | None = None) -> dict:
    if isinstance(data, list):
        response = {"data": data}
        if meta:
            response.update(meta)
        return response
    return {"data": data}


def create_list_response(
    data: list[dict],
    total: int,
    page: int,
    page_size: int,
    formatter: Callable | None = None,
) -> dict:
    pages = (total + page_size - 1) // page_size
    meta = {"total": total, "page": page, "pages": pages, "page_size": page_size}

    if formatter:
        return formatter(data, meta)
    return default_formatter(data, meta)


def create_item_response(data: dict, formatter: Callable | None = None) -> dict:
    if formatter:
        return formatter(data, None)
    return default_formatter(data)
