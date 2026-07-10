"""Relation resolution between registered models."""

from __future__ import annotations

from flashapi.core.schema import ModelSchema, RelationSchema


def resolve_relations(schemas: list[ModelSchema]) -> dict[str, list[RelationSchema]]:
    """
    Detect relations between models based on field names ending with _id.
    Returns a mapping: parent_plural -> list of child relations.

    Example: Book has author_id → Author is parent, Book is child.
    So "authors" -> [RelationSchema(type="one_to_many", target="books")]
    """
    schema_map = {s.name.lower(): s for s in schemas}

    parent_to_children: dict[str, list[RelationSchema]] = {}

    for schema in schemas:
        for field in schema.fields:
            if field.name.endswith("_id") and not field.primary_key:
                ref_name = field.name[:-3]  # "author_id" → "author"

                target_schema = schema_map.get(ref_name)
                if target_schema is None:
                    continue

                relation = RelationSchema(
                    type="one_to_many",
                    target=schema.plural,
                    target_plural=schema.plural,
                    foreign_key=field.name,
                )

                parent_plural = target_schema.plural
                if parent_plural not in parent_to_children:
                    parent_to_children[parent_plural] = []
                parent_to_children[parent_plural].append(relation)

                field.relation = RelationSchema(
                    type="many_to_one",
                    target=target_schema.name,
                    target_plural=target_schema.plural,
                    foreign_key=field.name,
                )

    return parent_to_children


def find_expandable_fields(schema: ModelSchema) -> dict[str, str]:
    """
    Return a mapping of expandable field names to their target plural.
    Example: {"author": "authors"} for a Book model with author_id.
    """
    expandable = {}
    for field in schema.fields:
        if field.relation and field.relation.type == "many_to_one":
            ref_name = field.name[:-3]  # "author_id" → "author"
            expandable[ref_name] = field.relation.target_plural
    return expandable
