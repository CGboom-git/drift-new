from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .delegation import DelegationDetector
from .records import SourceRecord, ValidationTraceEntry


class SourceLabelStore:
    URL_RE = re.compile(r"https?://[^\s<>'\"),\]]+", re.IGNORECASE)
    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    AMOUNT_RE = re.compile(r"(?<!\w)(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:USD|EUR|GBP|CNY|RMB|dollars?|euros?|pounds?))\b", re.IGNORECASE)
    DATE_RE = re.compile(
        r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4}|"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})\b",
        re.IGNORECASE,
    )
    FILE_RE = re.compile(r"(?:[\w./\\-]+)?[\w.-]+\.(?:txt|md|csv|json|yaml|yml|pdf|docx?|xlsx?|html?|py|js|ts)\b", re.IGNORECASE)
    CHANNEL_RE = re.compile(r"(?<!\w)[#@][A-Za-z][\w.-]{1,63}\b")
    PERSON_RE = re.compile(r"\b(?:user|person|sender|recipient|from|to|by)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})\b")

    def __init__(self) -> None:
        self.delegation_detector = DelegationDetector()
        self.reset()

    def reset(self) -> None:
        self.records: list[SourceRecord] = []
        self.validation_trace: list[ValidationTraceEntry] = []
        self._counter = 0
        self._raw_output_ids: dict[tuple[str, int], str] = {}
        self._run_started_at = datetime.now(timezone.utc).isoformat()

    def record_user_query(self, user_query: str) -> str:
        source_id = self._next_id("user_query")
        record = SourceRecord(
            source_id=source_id,
            step=0,
            owner="user",
            value=user_query,
            tool=None,
            source_kind="user_query",
            source_labels=["user_explicit"],
            evidence={"input": "user_query"},
            confidence=1.0,
            normalized_value=self._normalize(user_query),
            sanitized_visible=True,
        )
        self.records.append(record)
        self.validation_trace.append(
            ValidationTraceEntry(step=0, event="record_user_query", source_ids=[source_id])
        )

        for anchor in self.delegation_detector.detect(user_query):
            self._add_record(
                step=0,
                owner="user",
                value=anchor.value,
                tool=None,
                source_kind=f"delegated_{anchor.anchor_kind}",
                parent_sources=[source_id],
                source_labels=anchor.labels,
                evidence={
                    **anchor.evidence,
                    "anchor_kind": anchor.anchor_kind,
                    "delegation_pattern": anchor.pattern,
                },
                confidence=0.85,
                sanitized_visible=True,
            )

        self.record_regex_entities("user_query", source_id, user_query, step=0, owner="user")
        return source_id

    def record_tool_raw_output(self, tool_name: str, output: Any, step: int) -> str:
        source_id = self._add_record(
            step=step,
            owner="tool",
            value=output,
            tool=tool_name,
            source_kind="tool_raw_output",
            parent_sources=[],
            source_labels=["tool_output", "raw_observation"],
            evidence={"tool_name": tool_name, "phase": "before_injection_isolation"},
            confidence=1.0,
            sanitized_visible=False,
        )
        self._raw_output_ids[(tool_name, step)] = source_id
        return source_id

    def record_injected_fragment(
        self,
        tool_name: str,
        raw_source_id: str | None,
        fragment: Any,
        step: int,
    ) -> str:
        parent_sources = [raw_source_id] if raw_source_id else []
        return self._add_record(
            step=step,
            owner="tool",
            value=fragment,
            tool=tool_name,
            source_kind="injected_fragment",
            parent_sources=parent_sources,
            source_labels=["tool_output", "injected_instruction"],
            evidence={"tool_name": tool_name, "phase": "injection_isolation"},
            confidence=0.9,
            sanitized_visible=False,
        )

    def record_structured_fields(
        self,
        tool_name: str,
        raw_source_id: str | None,
        output: Any,
        step: int,
    ) -> list[str]:
        fields = list(self._iter_structured_fields(output))
        source_ids = []
        for path, value in fields:
            source_ids.append(
                self._add_record(
                    step=step,
                    owner="tool",
                    value=value,
                    tool=tool_name,
                    source_kind="structured_field",
                    parent_sources=[raw_source_id] if raw_source_id else [],
                    source_labels=["tool_output", "structured_field"],
                    evidence={"field_path": path},
                    confidence=0.8,
                    sanitized_visible=None,
                )
            )
        return source_ids

    def record_regex_entities(
        self,
        tool_name: str,
        raw_source_id: str | None,
        text: Any,
        step: int,
        owner: str = "tool",
    ) -> list[str]:
        text_value = self._to_text(text)
        if not text_value:
            return []

        source_ids = []
        for entity_kind, regex in self._entity_regexes():
            seen_values: set[str] = set()
            for match in regex.finditer(text_value):
                value = self._match_value(entity_kind, match)
                if not value:
                    continue
                value = value.rstrip(".,;:")
                key = value.lower()
                if key in seen_values:
                    continue
                seen_values.add(key)
                source_ids.append(
                    self._add_record(
                        step=step,
                        owner=owner,
                        value=value,
                        tool=tool_name,
                        source_kind=f"regex_{entity_kind}",
                        parent_sources=[raw_source_id] if raw_source_id else [],
                        source_labels=[owner + "_explicit" if owner == "user" else "tool_output", f"entity:{entity_kind}"],
                        evidence={
                            "span": f"{match.start()}:{match.end()}",
                            "extractor": entity_kind,
                            "excerpt": self._excerpt(text_value, match.start(), match.end()),
                        },
                        confidence=0.65,
                        sanitized_visible=None,
                    )
                )
        return source_ids

    def find_sources_by_value(self, value: Any) -> list[SourceRecord]:
        normalized = self._normalize(value)
        if not normalized:
            return []
        return [
            record
            for record in self.records
            if normalized in record.normalized_value or record.normalized_value in normalized
        ]

    def mark_raw_output_sanitized_visible(self, tool_name: str, step: int, visible: bool) -> None:
        source_id = self._raw_output_ids.get((tool_name, step))
        if not source_id:
            return
        for record in self.records:
            if record.source_id == source_id:
                record.sanitized_visible = visible
                break

    def export_log(self) -> dict[str, Any]:
        return {
            "version": 1,
            "run_started_at": self._run_started_at,
            "records": [record.to_dict() for record in self.records],
            "validation_trace": [entry.to_dict() for entry in self.validation_trace],
        }

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.export_log(), f, indent=2, ensure_ascii=False)

    def _add_record(
        self,
        step: int,
        owner: str,
        value: Any,
        tool: str | None,
        source_kind: str,
        parent_sources: list[str],
        source_labels: list[str],
        evidence: dict[str, Any],
        confidence: float,
        sanitized_visible: bool | None,
    ) -> str:
        source_id = self._next_id(source_kind)
        record = SourceRecord(
            source_id=source_id,
            step=step,
            owner=owner,
            value=value,
            tool=tool,
            source_kind=source_kind,
            parent_sources=parent_sources,
            source_labels=self._dedupe(source_labels),
            evidence=evidence,
            confidence=confidence,
            normalized_value=self._normalize(value),
            sanitized_visible=sanitized_visible,
        )
        self.records.append(record)
        self.validation_trace.append(
            ValidationTraceEntry(step=step, event=f"record_{source_kind}", source_ids=[source_id])
        )
        return source_id

    def _entity_regexes(self) -> tuple[tuple[str, re.Pattern[str]], ...]:
        return (
            ("url", self.URL_RE),
            ("email", self.EMAIL_RE),
            ("amount", self.AMOUNT_RE),
            ("date", self.DATE_RE),
            ("file", self.FILE_RE),
            ("channel", self.CHANNEL_RE),
            ("person", self.PERSON_RE),
        )

    def _iter_structured_fields(self, output: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
        if isinstance(output, str):
            parsed = self._try_parse_json(output)
            if parsed is None:
                return []
            output = parsed

        fields: list[tuple[str, Any]] = []
        if isinstance(output, dict):
            for key, value in output.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, (dict, list, tuple)):
                    fields.extend(self._iter_structured_fields(value, path))
                else:
                    fields.append((path, value))
        elif isinstance(output, (list, tuple)):
            for idx, value in enumerate(output):
                path = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
                if isinstance(value, (dict, list, tuple)):
                    fields.extend(self._iter_structured_fields(value, path))
                else:
                    fields.append((path, value))
        return fields

    def _try_parse_json(self, value: str) -> Any:
        stripped = value.strip()
        if not stripped or stripped[0] not in "[{":
            return None
        try:
            return json.loads(stripped)
        except Exception:
            return None

    def _match_value(self, entity_kind: str, match: re.Match[str]) -> str:
        if entity_kind == "person" and match.lastindex:
            return match.group(1)
        return match.group(0)

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        safe_prefix = re.sub(r"[^a-zA-Z0-9_]+", "_", prefix).strip("_") or "source"
        return f"{safe_prefix}_{self._counter:05d}"

    def _normalize(self, value: Any) -> str:
        text = self._to_text(value)
        return re.sub(r"\s+", " ", text).strip().lower()

    def _to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, sort_keys=True, ensure_ascii=False)
        except TypeError:
            if hasattr(value, "__dict__"):
                try:
                    return json.dumps(asdict(value), sort_keys=True, ensure_ascii=False)
                except Exception:
                    pass
            return str(value)

    def _excerpt(self, text: str, start: int, end: int, radius: int = 60) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        return text[left:right]

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
