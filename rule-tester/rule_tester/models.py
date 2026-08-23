"""Shared evidence models."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueryOutput:
    columns: tuple[tuple[str, int], ...]
    rows: tuple[tuple[Any, ...], ...]
    truncated: bool = False


@dataclass(frozen=True)
class EquivalenceEvidence:
    equivalent: bool
    ordered: bool
    original_row_count: int | None
    candidate_row_count: int | None
    reason_code: str
