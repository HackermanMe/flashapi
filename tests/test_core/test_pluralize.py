import pytest
from flashapi.core.pluralize import pluralize


@pytest.mark.parametrize("word,expected", [
    ("user", "users"),
    ("book", "books"),
    ("category", "categories"),
    ("city", "cities"),
    ("bus", "buses"),
    ("box", "boxes"),
    ("church", "churches"),
    ("wish", "wishes"),
    ("buzz", "buzzes"),
    ("leaf", "leaves"),
    ("wolf", "wolves"),
    ("person", "people"),
    ("child", "children"),
    ("mouse", "mice"),
    ("man", "men"),
    ("woman", "women"),
    ("tooth", "teeth"),
    ("foot", "feet"),
    ("datum", "data"),
    ("index", "indices"),
    ("day", "days"),
    ("key", "keys"),
    ("toy", "toys"),
])
def test_pluralize(word, expected):
    assert pluralize(word) == expected
