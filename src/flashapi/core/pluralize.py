"""Simple English pluralization rules."""

IRREGULARS = {
    "person": "people",
    "child": "children",
    "mouse": "mice",
    "goose": "geese",
    "man": "men",
    "woman": "women",
    "tooth": "teeth",
    "foot": "feet",
    "datum": "data",
    "index": "indices",
}


def pluralize(word: str) -> str:
    lower = word.lower()

    if lower in IRREGULARS:
        return IRREGULARS[lower]

    if lower.endswith(("s", "x", "z", "sh", "ch")):
        return lower + "es"

    if lower.endswith("y") and lower[-2:-1] not in "aeiou":
        return lower[:-1] + "ies"

    if lower.endswith("f"):
        return lower[:-1] + "ves"

    if lower.endswith("fe"):
        return lower[:-2] + "ves"

    return lower + "s"
