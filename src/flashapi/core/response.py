"""Response formatting."""

from typing import Callable


def create_list_response(
    data: list[dict],
    total: int,
    page: int,
    size: int,
    formatter: Callable | None = None,
) -> dict:
    total_pages = (total + size - 1) // size if size > 0 else 0
    response = {
        "data": data,
        "meta": {
            "page": page,
            "size": size,
            "totalElements": total,
            "totalPages": total_pages,
        },
    }
    if formatter:
        return formatter(response)
    return response


def create_item_response(data: dict, formatter: Callable | None = None) -> dict:
    response = {"data": data}
    if formatter:
        return formatter(response)
    return response


def create_error_response(message: str, status: int) -> dict:
    return {"error": message, "status": status}
