from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DelegatedAnchor:
    value: str
    anchor_kind: str
    pattern: str
    labels: list[str]
    evidence: dict[str, str]


class DelegationDetector:
    URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>'\"),\]]+", re.IGNORECASE)
    EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    FILE_RE = re.compile(r"(?:[\w./\\-]+)?[\w.-]+\.(?:txt|md|csv|json|yaml|yml|pdf|docx?|xlsx?|html?)\b", re.IGNORECASE)

    DELEGATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("do_all_tasks_on", re.compile(r"\bdo\s+all\s+tasks\s+on\b", re.IGNORECASE)),
        ("do_all_tasks_in", re.compile(r"\bdo\s+all\s+tasks\s+in\b", re.IGNORECASE)),
        ("do_all_tasks_from", re.compile(r"\bdo\s+all\s+tasks\s+from\b", re.IGNORECASE)),
        ("actions_specified_in", re.compile(r"\bdo\s+the\s+actions\s+specified\s+in\b", re.IGNORECASE)),
        ("perform_the_actions", re.compile(r"\bperform\s+the\s+actions?\s+(?:specified|listed|described)\s+in\b", re.IGNORECASE)),
        ("follow_instructions_in", re.compile(r"\bfollow\s+the\s+instructions\s+in\b", re.IGNORECASE)),
        ("instructions_in", re.compile(r"\binstructions?\s+(?:in|on|from|at)\b", re.IGNORECASE)),
        ("todo_list_at", re.compile(r"\b(?:todo|to-do)\s+list\s+(?:at|in|on)\b", re.IGNORECASE)),
        ("email_from_subject", re.compile(r"\bemail\s+from\b.*\b(?:with\s+)?subject\b", re.IGNORECASE | re.DOTALL)),
        ("specific_email", re.compile(r"\b(?:the\s+)?(?:specific\s+)?email\s+(?:from|by)\b", re.IGNORECASE)),
        ("document_containing", re.compile(r"\b(?:document|file|page)\s+(?:containing|with|that\s+has)\b", re.IGNORECASE)),
    )

    def has_delegation(self, user_query: str) -> bool:
        if not user_query:
            return False
        return any(pattern.search(user_query) for _, pattern in self.DELEGATION_PATTERNS)

    def detect(self, user_query: str) -> list[DelegatedAnchor]:
        if not user_query:
            return []

        anchors: list[DelegatedAnchor] = []
        matched_patterns = [name for name, pattern in self.DELEGATION_PATTERNS if pattern.search(user_query)]
        if not matched_patterns:
            return anchors

        labels = [
            "user_explicit",
            "task_anchor",
            "user_specified_source",
            "delegated_task_source",
        ]

        seen: set[tuple[str, str]] = set()
        for kind, regex in (
            ("url", self.URL_RE),
            ("email", self.EMAIL_RE),
            ("file", self.FILE_RE),
        ):
            for match in regex.finditer(user_query):
                value = match.group(0).rstrip(".,;:")
                key = (kind, value.lower())
                if key in seen:
                    continue
                seen.add(key)
                anchors.append(
                    DelegatedAnchor(
                        value=value,
                        anchor_kind=kind,
                        pattern=matched_patterns[0],
                        labels=list(labels),
                        evidence={
                            "matched_pattern": matched_patterns[0],
                            "span": f"{match.start()}:{match.end()}",
                            "query_excerpt": self._excerpt(user_query, match.start(), match.end()),
                        },
                    )
                )

        return anchors

    def _excerpt(self, text: str, start: int, end: int, radius: int = 60) -> str:
        left = max(0, start - radius)
        right = min(len(text), end + radius)
        return text[left:right]
