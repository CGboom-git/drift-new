"""Immutable JSON snapshots: caller mutations cannot change a constraint."""
from dataclasses import dataclass, asdict
import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


@dataclass(frozen=True)
class ConstraintSpec:
    task_id: str
    consumer_step_id: str | None
    tool: str
    fixed_constraints: str
    parameter_roles: str
    binding_rules: str
    recovery_scope: str
    source_annotations: str

    @classmethod
    def create(cls, task_id, consumer_step_id, tool, fixed_constraints=None,
               parameter_roles=None, binding_rules=None, recovery_scope=None, source_annotations=None):
        return cls(task_id, consumer_step_id, tool, *[canonical(x) for x in
            (fixed_constraints or [], parameter_roles or {}, binding_rules or [],
             recovery_scope or [], source_annotations or {})])

    @property
    def constraint_id(self):
        return digest(asdict(self))


@dataclass(frozen=True)
class Call:
    task_id: str
    call_id: str
    tool: str
    arguments: str
    position: int
    epoch: int = 0

    @classmethod
    def create(cls, task_id, call_id, tool, arguments, position, epoch=0):
        return cls(task_id, call_id, tool, canonical(arguments), position, epoch)


@dataclass(frozen=True)
class Evidence:
    task_id: str
    source_id: str
    call_id: str
    tool: str
    request: str
    payload: str
    position: int
    epoch: int
    success: bool
    revision: int


@dataclass(frozen=True)
class Witness:
    call_id: str
    tool: str
    parameter_name: str
    parameter_value: str
    constraint_id: str
    evidence_source_id: str | None
    evidence_origin: str
    parameter_role: str
    relation_type: str
    temporal_available: bool | None
    verdict: str
    reason: str
    rule_id: str
    authority_basis: str
    evidence_revision: int | None = None


@dataclass(frozen=True)
class Decision:
    verdict: str
    witnesses: tuple[Witness, ...]
    missing_evidence_conditions: tuple[str, ...]
    call_fingerprint: str
    constraint_id: str
    evidence_revision: int

    def json(self):
        return asdict(self)
