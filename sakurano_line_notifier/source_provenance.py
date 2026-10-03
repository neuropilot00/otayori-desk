"""Offline review-evidence consistency gate; not a claim of live source coverage."""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from urllib.parse import urlparse


def registry_fingerprint(source: dict) -> str:
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def validate_provenance(registry: dict, review: dict) -> None:
    """Require deliberate evidence updates when a source or its ownership changes.

    Unverified endpoints remain valid *research records*, never verified data.
    This gate detects drift; a maintainer must still review the official evidence.
    """
    if review.get("schema_version") != "1.0" or review.get("research_only") is not True:
        raise ValueError("unsupported source research contract")
    raw_sources = registry.get("sources")
    records = review.get("sources")
    evidence = review.get("evidence")
    if not isinstance(raw_sources, list) or not isinstance(records, list) or not isinstance(evidence, dict):
        raise ValueError("invalid registry or review evidence")
    for evidence_id, item in evidence.items():
        if (not isinstance(item, dict)
                or any(not isinstance(item.get(key), str) or not item[key].strip()
                       for key in ("url", "title", "publisher", "finding", "checked_on"))
                or item.get("verification_status") not in {"verified", "partially_verified", "unverified"}):
            raise ValueError(f"invalid supporting evidence: {evidence_id}")
        try:
            url = urlparse(item["url"])
            date.fromisoformat(item["checked_on"])
            safe = url.scheme in {"http", "https"} and bool(url.hostname) and not url.username and not url.password
        except ValueError:
            safe = False
        if not safe:
            raise ValueError(f"invalid supporting evidence location/date: {evidence_id}")
    for entries in (raw_sources, records):
        id_key = "id" if entries is raw_sources else "source_id"
        if any(not isinstance(row, dict) or not isinstance(row.get(id_key), str) for row in entries):
            raise ValueError("invalid source identity")
        if any(count != 1 for count in Counter(row[id_key] for row in entries).values()):
            raise ValueError("duplicate source review identity")
    by_id = {row["source_id"]: row for row in records}
    if set(by_id) != {row["id"] for row in raw_sources}:
        raise ValueError("source review inventory differs from registry")
    for raw in raw_sources:
        source_id = raw["id"]
        record = by_id[source_id]
        if record.get("registry_fingerprint_sha256") != registry_fingerprint(raw):
            raise ValueError(f"source {source_id}: review fingerprint is stale")
        if record.get("collection_id") != raw.get("collection_id", source_id):
            raise ValueError(f"source {source_id}: reviewed collection differs")
        endpoints = record.get("endpoints")
        urls = raw.get("page_urls", [raw.get("page_url")])
        if not isinstance(endpoints, list) or [row.get("url") for row in endpoints] != urls:
            raise ValueError(f"source {source_id}: reviewed endpoints differ")
        identity = record.get("identity", {})
        if raw.get("collection_root", True) and raw.get("source_group", "school") == "school":
            if (identity.get("status") != "verified" or identity.get("entity_type") != "school"
                    or identity.get("municipality") != raw["ward"] or identity.get("school_type") != raw["level"]
                    or not identity.get("official_name") or not identity.get("evidence_ids")):
                raise ValueError(f"school {source_id}: official identity review required")
            if not any(evidence.get(ref, {}).get("verification_status") == "verified"
                       for ref in identity["evidence_ids"]):
                raise ValueError(f"school {source_id}: verified supporting evidence required")
        for endpoint in endpoints:
            if endpoint.get("reachability", {}).get("status") not in {"reachable", "unreachable", "unverified"}:
                raise ValueError(f"source {source_id}: invalid reachability evidence")
            if endpoint.get("content_readability", {}).get("status") not in {"readable", "partially_readable", "unreadable", "unverified"}:
                raise ValueError(f"source {source_id}: invalid readability evidence")
    # Evidence references must resolve independently of registry hash matching.
    def check_refs(value: object) -> None:
        if isinstance(value, dict):
            if "evidence_ids" in value:
                refs = value["evidence_ids"]
                if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in evidence for ref in refs):
                    raise ValueError("dangling source evidence reference")
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)
    check_refs(review)
