from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceRecord:
    source_id: str
    step: int
    owner: str
    value: Any
    tool: str | None
    source_kind: str
    parent_sources: list[str] = field(default_factory=list)
    source_labels: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    normalized_value: str = ""
    sanitized_visible: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Compatibility alias for earlier experiments that used fact_marks.
        data["fact_marks"] = list(self.source_labels)
        return data


@dataclass
class ValidationTraceEntry:
    step: int
    event: str
    source_ids: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    decision: str = "log_only"
    would_reject: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
