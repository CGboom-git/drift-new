from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SinkSpec:
    sink: str
    mode: str
    expected_values: list[Any] = field(default_factory=list)
    expected_root_tools: list[str] = field(default_factory=list)
    placeholder: str | None = None
    semantic_type: str | None = None
    sink_role: str | None = None
    compile_confidence: float = 0.5
    fallback_behavior: str = "warn"
    raw_condition: Any = None
    raw_required_value: Any = None


class FlowExpectationCompiler:
    MODES = {
        "constant_check",
        "placeholder_origin_check",
        "origin_check",
        "synthesis_allowed",
        "track_only",
    }

    PLACEHOLDER_RE = re.compile(
        r"(?:^|[\s_-])(?:summary|content|extracted|selected|chosen|new|target|"
        r"colleague|username|url|email|amount|date|file|document|channel)(?:$|[\s_-])",
        re.IGNORECASE,
    )
    ROOT_TOOL_RE = re.compile(
        r"(?:from|by|via|using|obtained\s+from|extracted\s+from|read\s+from)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    )
    TOOL_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")

    def __init__(self, contract_helper=None) -> None:
        self.contract_helper = contract_helper

    def compile(
        self,
        node_checklist: Any,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
    ) -> list[SinkSpec]:
        nodes = self._parse_nodes(node_checklist)
        specs: list[SinkSpec] = []

        for node in nodes:
            node_name = str(node.get("name") or "")
            if tool_name and node_name and node_name != tool_name:
                continue
            required = node.get("required parameters") or node.get("required_parameters") or {}
            conditions = node.get("conditions") or {}
            if not isinstance(required, dict):
                required = {}
            if not isinstance(conditions, dict):
                conditions = {}

            arg_names = set(required.keys()) | set(conditions.keys())
            if tool_args:
                arg_names |= set(tool_args.keys())
            for arg_name in sorted(arg_names):
                specs.append(
                    self._compile_arg(
                        tool_name=node_name or tool_name or "unknown_tool",
                        arg_name=arg_name,
                        required_value=required.get(arg_name),
                        condition=conditions.get(arg_name),
                    )
                )

        if specs or not tool_name or not tool_args:
            return specs

        return [
            self._compile_arg(tool_name=tool_name, arg_name=arg_name, required_value=None, condition=None)
            for arg_name in sorted(tool_args.keys())
        ]

    def spec_map(
        self,
        node_checklist: Any,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> dict[str, SinkSpec]:
        return {spec.sink: spec for spec in self.compile(node_checklist, tool_name, tool_args)}

    def _compile_arg(
        self,
        tool_name: str,
        arg_name: str,
        required_value: Any,
        condition: Any,
    ) -> SinkSpec:
        sink = f"{tool_name}.{arg_name}"
        raw_text = " ".join(
            text for text in [self._stringify(required_value), self._stringify(condition)] if text
        )
        expected_roots = self._extract_root_tools(raw_text)
        semantic_type = self._semantic_type(arg_name, required_value)
        sink_role = self._sink_role(tool_name, arg_name)
        placeholder = self._placeholder(required_value, raw_text)
        is_content = self._is_content_arg(tool_name, arg_name)

        if required_value is None and not expected_roots and not placeholder:
            mode = "track_only"
            confidence = 0.2
        elif expected_roots and is_content:
            mode = "synthesis_allowed"
            confidence = 0.75
        elif expected_roots and placeholder:
            mode = "placeholder_origin_check"
            confidence = 0.75
        elif expected_roots:
            mode = "origin_check"
            confidence = 0.7
        elif placeholder:
            mode = "placeholder_origin_check"
            confidence = 0.45
        elif self._is_explicit_constant(required_value):
            mode = "constant_check"
            confidence = 0.9
        else:
            mode = "track_only"
            confidence = 0.25

        return SinkSpec(
            sink=sink,
            mode=mode,
            expected_values=[required_value] if self._is_explicit_constant(required_value) else [],
            expected_root_tools=expected_roots,
            placeholder=placeholder,
            semantic_type=semantic_type,
            sink_role=sink_role,
            compile_confidence=confidence,
            fallback_behavior="warn" if mode == "track_only" else "validate",
            raw_condition=condition,
            raw_required_value=required_value,
        )

    def _parse_nodes(self, node_checklist: Any) -> list[dict[str, Any]]:
        if node_checklist in (None, "", "None"):
            return []
        if isinstance(node_checklist, list):
            return [node for node in node_checklist if isinstance(node, dict)]
        if isinstance(node_checklist, dict):
            return [node_checklist]
        if isinstance(node_checklist, str):
            try:
                parsed = json.loads(node_checklist)
            except Exception:
                return []
            return self._parse_nodes(parsed)
        return []

    def _extract_root_tools(self, text: str) -> list[str]:
        if not text:
            return []
        roots: list[str] = []
        for match in self.ROOT_TOOL_RE.finditer(text):
            roots.append(match.group(1))
        if not roots:
            for token in self.TOOL_TOKEN_RE.findall(text):
                if "_" in token and token.lower() not in {"summary_content", "extracted_url"}:
                    roots.append(token)
        return self._dedupe(roots)

    def _placeholder(self, required_value: Any, raw_text: str) -> str | None:
        value_text = self._stringify(required_value)
        if value_text and self.PLACEHOLDER_RE.search(value_text):
            return value_text
        if raw_text and self.PLACEHOLDER_RE.search(raw_text) and not self._is_explicit_constant(required_value):
            return value_text or raw_text
        return None

    def _is_explicit_constant(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, (int, float, bool)):
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return False
            if self.ROOT_TOOL_RE.search(stripped) or self.PLACEHOLDER_RE.search(stripped):
                return False
            if re.fullmatch(r"\{.*\}", stripped):
                return False
            return True
        return False

    def _semantic_type(self, arg_name: str, required_value: Any) -> str:
        name = arg_name.lower()
        value = self._stringify(required_value).lower()
        text = f"{name} {value}"
        for semantic in ("url", "email", "amount", "date", "channel", "file", "document", "recipient"):
            if semantic in text:
                return semantic
        if self._is_content_arg("", arg_name):
            return "content"
        return "unknown"

    def _sink_role(self, tool_name: str, arg_name: str) -> str:
        if self.contract_helper is not None:
            try:
                return self.contract_helper.get_arg_role(tool_name, arg_name)
            except Exception:
                pass
        return "content" if self._is_content_arg(tool_name, arg_name) else "argument"

    def _is_content_arg(self, tool_name: str, arg_name: str) -> bool:
        if self.contract_helper is not None:
            try:
                return self.contract_helper.is_content_arg(tool_name, arg_name)
            except Exception:
                pass
        return arg_name.lower() in {"body", "content", "message", "summary", "description", "subject"}

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result
