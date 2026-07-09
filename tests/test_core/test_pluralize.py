import pytest
from flashapi.core.pluralize import pluralize


@pytest.mark.parametrize("word,expected", [
    # English
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
    ("class", "classes"),
    ("match", "matches"),
    ("dish", "dishes"),
    # French
    ("niveau", "niveaux"),
    ("jeu", "jeux"),
    ("animal", "animaux"),
    ("journal", "journaux"),
    ("travail", "travaux"),
    ("emploidutemps", "emploidutemps"),
    ("voix", "voix"),
    ("nez", "nez"),
    ("enseignant", "enseignants"),
    ("eleve", "eleves"),
    ("matiere", "matieres"),
    ("evaluation", "evaluations"),
    ("motif", "motifs"),
    ("objectif", "objectifs"),
    ("chef", "chefs"),
    ("bulletin", "bulletins"),
])
def test_pluralize(word, expected):
    assert pluralize(word) == expected
