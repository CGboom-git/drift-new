from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .compiler import SinkSpec


@dataclass
class SinkEvidence:
    sink: str
    value: Any
    matched_sources: list[str] = field(default_factory=list)
    actual_origin_tools: list[str] = field(default_factory=list)
    actual_origin_paths: list[str] = field(default_factory=list)
    source_labels: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    resolution_status: str = "unknown_origin"


class SinkEvidenceResolver:
    def resolve_args(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        compiled_sink_specs: dict[str, SinkSpec],
        source_store,
        contract_helper,
    ) -> dict[str, SinkEvidence]:
        result: dict[str, SinkEvidence] = {}
        for arg_name, value in tool_args.items():
            sink = f"{tool_name}.{arg_name}"
            if isinstance(value, list):
                for idx, elem in enumerate(value):
                    item_sink = f"{sink}[{idx}]"
                    result[item_sink] = self.resolve_arg(
                        tool_name=tool_name,
                        arg_name=arg_name,
                        value=elem,
                        sink_spec=compiled_sink_specs.get(sink),
                        source_store=source_store,
                        contract_helper=contract_helper,
                    )
            result[sink] = self.resolve_arg(
                tool_name=tool_name,
                arg_name=arg_name,
                value=value,
                sink_spec=compiled_sink_specs.get(sink),
                source_store=source_store,
                contract_helper=contract_helper,
            )
        return result

    def resolve_arg(
        self,
        tool_name: str,
        arg_name: str,
        value: Any,
        sink_spec: SinkSpec | None,
        source_store,
        contract_helper,
    ) -> SinkEvidence:
        sink = f"{tool_name}.{arg_name}"
        normalized = self._normalize(value)
        if not normalized:
            return SinkEvidence(
                sink=sink,
                value=value,
                source_labels=["unknown_origin"],
                resolution_status="empty_value",
            )

        high_risk = contract_helper.is_high_risk_arg(tool_name, arg_name)
        content_like = contract_helper.is_content_arg(tool_name, arg_name) and not high_risk
        records = list(getattr(source_store, "records", []))
        normalized_candidates = self._candidate_normalizations(value)

        match_groups = [
            ("normalized_exact_match", self._exact_matches(records, normalized_candidates), 0.95),
            ("structured_field_match", self._kind_matches(records, normalized_candidates, {"structured_field"}), 0.9),
            ("regex_entity_match", self._regex_matches(records, normalized_candidates), 0.85),
        ]
        if not high_risk or len(normalized) >= 8:
            match_groups.append(("substring_match", self._substring_matches(records, normalized), 0.55))

        for status, matches, confidence in match_groups:
            if matches:
                clean = [m for m in matches if "injected_instruction" not in set(getattr(m, "source_labels", []))]
                if clean:
                    return self._from_matches(sink, value, matches, status, confidence,
                                              extra_labels=["clean_support_preferred"])
                return self._from_matches(sink, value, matches, status, confidence)

        if high_risk and not content_like:
            selection_words = {"most", "largest", "highest", "best", "smallest", "cheapest",
                                "latest", "newest", "nearest", "closest", "select", "choose", "pick"}
            read_outputs = [
                r for r in records
                if r.source_kind in ("tool_raw_output", "tool_sanitized_output", "structured_field")
                and "injected_instruction" not in set(r.source_labels)
            ]
            selection_value_in_output = any(
                normalized in r.normalized_value or r.normalized_value in normalized
                for r in read_outputs
            )
            if selection_value_in_output:
                return SinkEvidence(
                    sink=sink,
                    value=value,
                    matched_sources=[r.source_id for r in read_outputs if normalized in r.normalized_value or r.normalized_value in normalized],
                    actual_origin_tools=list(set(r.tool for r in read_outputs if r.tool)),
                    source_labels=["tool_output", "selection_from_read_result"],
                    evidence=[{"source_id": r.source_id, "source_kind": r.source_kind} for r in read_outputs[:3]],
                    confidence=0.5,
                    resolution_status="selection_from_read_result",
                )

        if content_like:
            expected_roots = sink_spec.expected_root_tools if sink_spec else []
            root_records = [
                record
                for record in records
                if record.tool in expected_roots
                and "injected_instruction" not in set(record.source_labels)
            ]
            if expected_roots and root_records:
                return self._from_matches(
                    sink,
                    value,
                    root_records,
                    "possible_synthesis",
                    0.45,
                    extra_labels=["llm_synthesis"],
                )
            return SinkEvidence(
                sink=sink,
                value=value,
                source_labels=["unknown_origin", "llm_synthesis"],
                confidence=0.25,
                resolution_status="llm_synthesis",
            )

        return SinkEvidence(
            sink=sink,
            value=value,
            source_labels=["unknown_origin", "model_generated"],
            confidence=0.1,
            resolution_status="model_generated",
        )

    def _exact_matches(self, records: list[Any], normalized_values: list[str]) -> list[Any]:
        normalized_set = set(normalized_values)
        return [
            record
            for record in records
            if normalized_set & set(self._candidate_normalizations(record.value))
        ]

    def _kind_matches(self, records: list[Any], normalized_values: list[str], kinds: set[str]) -> list[Any]:
        normalized_set = set(normalized_values)
        return [
            record
            for record in records
            if record.source_kind in kinds
            and normalized_set & set(self._candidate_normalizations(record.value))
        ]

    def _regex_matches(self, records: list[Any], normalized_values: list[str]) -> list[Any]:
        normalized_set = set(normalized_values)
        return [
            record
            for record in records
            if record.source_kind.startswith("regex_")
            and normalized_set & set(self._candidate_normalizations(record.value))
        ]

    def _substring_matches(self, records: list[Any], normalized: str) -> list[Any]:
        if len(normalized) < 3:
            return []
        return [
            record
            for record in records
            if normalized in record.normalized_value or record.normalized_value in normalized
        ]

    def _from_matches(
        self,
        sink: str,
        value: Any,
        matches: list[Any],
        status: str,
        confidence: float,
        extra_labels: list[str] | None = None,
    ) -> SinkEvidence:
        labels: list[str] = []
        tools: list[str] = []
        paths: list[str] = []
        evidence: list[dict[str, Any]] = []
        source_ids: list[str] = []

        for record in matches:
            source_ids.append(record.source_id)
            labels.extend(record.source_labels)
            if record.tool:
                tools.append(record.tool)
            field_path = record.evidence.get("field_path") or record.source_kind
            paths.append(str(field_path))
            evidence.append(
                {
                    "source_id": record.source_id,
                    "source_kind": record.source_kind,
                    "tool": record.tool,
                    "labels": list(record.source_labels),
                    "field_path": record.evidence.get("field_path"),
                }
            )

        if extra_labels:
            labels.extend(extra_labels)

        return SinkEvidence(
            sink=sink,
            value=value,
            matched_sources=self._dedupe(source_ids),
            actual_origin_tools=self._dedupe(tools),
            actual_origin_paths=self._dedupe(paths),
            source_labels=self._dedupe(labels),
            evidence=evidence,
            confidence=confidence,
            resolution_status=status,
        )

    def _normalize(self, value: Any) -> str:
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

    def _candidate_normalizations(self, value: Any) -> list[str]:
        candidates = [self._normalize(value)]
        amount_key = self._amount_key(value)
        if amount_key:
            candidates.append(amount_key)
        return self._dedupe([candidate for candidate in candidates if candidate])

    def _amount_key(self, value: Any) -> str | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float, Decimal)):
            return self._canonical_decimal(str(value))
        text = str(value)
        if not (
            re.fullmatch(r"\s*[+-]?\d[\d,]*(?:\.\d+)?\s*", text)
            or re.search(r"[$€£]|\b(?:amount|total|price|cost|usd|eur|gbp|cny|rmb|dollars?|euros?|pounds?)\b", text, re.IGNORECASE)
        ):
            return None
        match = re.search(r"[+-]?\d[\d,]*(?:\.\d+)?", text)
        if not match:
            return None
        return self._canonical_decimal(match.group(0).replace(",", ""))

    def _canonical_decimal(self, value: str) -> str | None:
        try:
            decimal = Decimal(value)
        except (InvalidOperation, ValueError):
            return None
        normalized = format(decimal.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
