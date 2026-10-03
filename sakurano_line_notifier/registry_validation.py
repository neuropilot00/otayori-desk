"""Validate collection ownership and explicit sharing before selecting sources."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .web_catalog import SourceConfig


def validate_source_relationships(sources: list[SourceConfig]) -> None:
    """Reject ambiguous graphs, including disabled entries, without inferring links.

    Collection IDs are registry keys, not institution IDs. Related links are
    directed: a source opts into the named collection, not its other relations.
    """
    ids: set[str] = set()
    roots: dict[str, SourceConfig] = {}
    for source in sources:
        if source.id in ids:
            raise ValueError(f"source ids must be unique: {source.id}")
        ids.add(source.id)
        if source.collection_root:
            previous = roots.get(source.collection_id)
            if previous is not None:
                raise ValueError(
                    f"collection {source.collection_id!r} has duplicate roots: "
                    f"{previous.id}, {source.id}"
                )
            roots[source.collection_id] = source

    for source in sources:
        root = roots.get(source.collection_id)
        if root is None:
            raise ValueError(
                f"source {source.id!r}: collection_id {source.collection_id!r} has no root"
            )
        if source.enabled and not root.enabled:
            raise ValueError(f"enabled source {source.id!r} has disabled collection root {root.id!r}")
        if source.ward != root.ward:
            raise ValueError(
                f"source {source.id!r}: ward does not match collection root {root.id!r}"
            )
        if source.source_group == "school" and root.source_group != "school":
            raise ValueError(f"school source {source.id!r} must have a school collection root")
        if source.source_group in {"school", "after_school"} and source.level != root.level:
            raise ValueError(
                f"source {source.id!r}: level does not match collection root {root.id!r}"
            )
        if source.shared_with_ward:
            # These are the existing city-wide after-school guidance types.
            # Facilities and school/club letters must remain explicitly scoped.
            common_after_school = (
                source.source_group == "after_school"
                and source.coverage_kind == "reference"
                and source.content_kind in {"gakudo_admissions", "asobee_reference"}
            )
            if source.source_group != "municipality" and not common_after_school:
                raise ValueError(
                    f"source {source.id!r}: shared_with_ward requires municipality "
                    "or common after-school reference material"
                )
        for collection_id in source.related_collections:
            target = roots.get(collection_id)
            if target is None:
                raise ValueError(
                    f"source {source.id!r}: related_collections contains an unknown "
                    f"collection root {collection_id!r}"
                )
            if source.ward != target.ward:
                raise ValueError(
                    f"source {source.id!r}: related_collections target {collection_id!r} "
                    "must be in the same ward"
                )
            if source.enabled and not target.enabled:
                raise ValueError(
                    f"enabled source {source.id!r}: related_collections target {collection_id!r} is disabled"
                )
            if (source.source_group != "municipality" and root.source_group == "school"
                    and target.source_group == "school" and collection_id != source.collection_id):
                raise ValueError(
                    f"source {source.id!r}: related_collections cannot share with another school "
                    f"collection {collection_id!r}"
                )
            if source.source_group == "school" and collection_id != source.collection_id and target.source_group != "after_school":
                raise ValueError(
                    f"school source {source.id!r}: related_collections cannot share with "
                    f"another school or municipality collection {collection_id!r}"
                )
            if source.source_group in {"school", "after_school"} and source.level != target.level:
                raise ValueError(
                    f"source {source.id!r}: related_collections target {collection_id!r} "
                    "must have the same level"
                )
