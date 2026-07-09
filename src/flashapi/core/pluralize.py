"""Pluralization rules supporting English and French model names.

Strategy:
- Irregulars dict handles all known exceptions for both languages.
- Rules are ordered to avoid cross-language conflicts.
- For genuinely ambiguous cases, users can override via Model(plural=...).
"""

IRREGULARS = {
    # English irregulars
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
    "leaf": "leaves",
    "knife": "knives",
    "wife": "wives",
    "life": "lives",
    "shelf": "shelves",
    "self": "selves",
    "half": "halves",
    "wolf": "wolves",
    # English words ending in -s/-x/-z that take -es (not invariable)
    "bus": "buses",
    "box": "boxes",
    "fox": "foxes",
    "buzz": "buzzes",
    "quiz": "quizzes",
    "fez": "fezzes",
    # French irregulars
    "travail": "travaux",
    "journal": "journaux",
    "oeil": "yeux",
    "monsieur": "messieurs",
    "madame": "mesdames",
}


def pluralize(word: str) -> str:
    lower = word.lower()

    if lower in IRREGULARS:
        return IRREGULARS[lower]

    # --- English: -ss, -sh, -ch → +es (must check before -s invariable rule) ---
    # en: class→classes, dish→dishes, match→matches
    if lower.endswith(("ss", "sh", "ch")):
        return lower + "es"

    # --- Invariable endings (both languages) ---
    # -s, -x, -z → no change (fr: temps, voix, nez / en: species)
    if lower.endswith(("s", "x", "z")):
        return lower

    # --- French rules ---

    # -eau, -au, -eu → +x (fr: niveau→niveaux, jeu→jeux, noyau→noyaux)
    if lower.endswith(("eau", "au", "eu")):
        return lower + "x"

    # -al → -aux (fr: animal→animaux, journal→journaux)
    # English exceptions (festival, carnival) are rare model names;
    # if needed, add them to IRREGULARS or use Model(plural=...)
    if lower.endswith("al"):
        return lower[:-2] + "aux"

    # consonant + y → -ies (en: category→categories, city→cities)
    if lower.endswith("y") and len(lower) >= 2 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"

    # --- Default: +s (works for both languages) ---
    # fr: maison→maisons, eleve→eleves, enseignant→enseignants
    # en: book→books, user→users, article→articles
    return lower + "s"
