"""TAER: Task-Anchored Ephemeral Repair - Data Models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BackboneStep:
    step_id: str
    original_index: int
    tool_name: str
    obligation: str
    authorized_effect: dict[str, Any] = field(default_factory=dict)
    required_parameters: dict[str, Any] = field(default_factory=dict)
    conditions: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


@dataclass
class RepairStep:
    repair_id: str
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    relation: str = "REPAIR"
    consumer_step_id: str | None = None
    missing_condition: str | None = None
    provides: str = ""
    control_sources: list[str] = field(default_factory=list)
    argument_sources: dict[str, list[str]] = field(default_factory=dict)
    scope_delta: str = "NONE"
    risk: str = "READ_ONLY"
    confidence: str = "LOW"
    status: str = "candidate"
    remaining_uses: int = 1
    depends_on_repair_ids: list[str] = field(default_factory=list)
    expected_effect: str | None = None
    source: str = "taer"


@dataclass
class TAERState:
    backbone_order: list[str] = field(default_factory=list)
    backbone_steps: dict[str, BackboneStep] = field(default_factory=dict)
    repair_steps: dict[str, RepairStep] = field(default_factory=dict)
    active_consumer_step_id: str | None = None
    pending_postcondition_repair_id: str | None = None
    initialized: bool = False
    candidate_count: int = 0
    direct_effect_count: int = 0
    repair_count: int = 0
    probe_count: int = 0
    new_goal_count: int = 0
    ambiguous_count: int = 0
    boundary_block_count: int = 0
    fallback_count: int = 0
    repair_success_count: int = 0
    repair_rollback_count: int = 0
