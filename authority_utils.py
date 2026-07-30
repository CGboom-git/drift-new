from __future__ import annotations

import json
import re
from typing import Any


AUTHORITY_TARGET_FIELDS = {
    "recipient",
    "recipients",
    "principal",
    "user",
    "username",
    "user_name",
    "user_email",
    "channel",
    "channel_name",
    "account",
    "account_id",
    "destination",
    "email",
    "url",
    "resource_id",
    "participant",
    "participants",
    "attendee",
    "attendees",
    "target",
    "selector",
    "file_id",
}


def normalize_authority_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_authority_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, sort_keys=True, ensure_ascii=False)
        except TypeError:
            text = str(value)
    return re.sub(r"\s+", " ", text).strip().lower()


def authority_value_variants(value: Any) -> list[str]:
    text = normalize_authority_value(value)
    if not text:
        return []
    variants = {text, text.rstrip("/")}
    if text.startswith("#"):
        variants.add(text[1:].strip())
    if text.startswith("www."):
        variants.add(text[4:].rstrip("/"))
    if text.startswith("https://"):
        variants.add(text.removeprefix("https://").rstrip("/"))
    if text.startswith("http://"):
        variants.add(text.removeprefix("http://").rstrip("/"))
    variants.discard("")
    return sorted(variants)


def is_authority_target_name(name: Any) -> bool:
    normalized = normalize_authority_key(name)
    if normalized in AUTHORITY_TARGET_FIELDS:
        return True
    if normalized.endswith("_name") and any(
        prefix in normalized for prefix in ("user", "channel", "recipient", "participant", "attendee")
    ):
        return True
    if normalized.endswith("_email") and any(prefix in normalized for prefix in ("user", "recipient")):
        return True
    if normalized.endswith("_id") and normalized in {"account_id", "file_id", "resource_id", "transaction_id", "event_id"}:
        return True
    return False


def iter_authority_values(value: Any):
    if not isinstance(value, dict):
        return
    for key, nested_value in value.items():
        if is_authority_target_name(key):
            yield from iter_leaf_values(nested_value)
        elif isinstance(nested_value, dict):
            yield from iter_authority_values(nested_value)
        elif isinstance(nested_value, (list, tuple, set)):
            for item in nested_value:
                if isinstance(item, dict):
                    yield from iter_authority_values(item)


def iter_leaf_values(value: Any):
    if isinstance(value, (list, tuple, set)):
        for item in value:
            yield from iter_leaf_values(item)
    elif isinstance(value, dict):
        for nested_value in value.values():
            yield from iter_leaf_values(nested_value)
    else:
        yield value
