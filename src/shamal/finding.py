"""Finding: the structured output of an investigation (spec: result-investigation)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Evidence(BaseModel):
    description: str
    metric: str | None = None
    window_start_s: float | None = None
    window_end_s: float | None = None


class Hypothesis(BaseModel):
    cause: str
    confidence: Literal["high", "medium", "low"]
    evidence: list[str] = []


class Finding(BaseModel):
    symptom: str
    evidence: list[Evidence] = []
    hypotheses: list[Hypothesis] = []
    next_steps: list[str] = []
    conclusive: bool = True
    notes: list[str] = []


def render_finding_text(finding: Finding) -> str:
    lines = ["=== Investigation Finding ==="]
    if not finding.conclusive:
        lines.append("(inconclusive - partial findings only)")
    lines.append(f"Symptom: {finding.symptom}")
    if finding.evidence:
        lines.append("Evidence:")
        for item in finding.evidence:
            window = ""
            if item.window_start_s is not None and item.window_end_s is not None:
                window = f" [{item.window_start_s:.0f}s-{item.window_end_s:.0f}s]"
            metric = f" ({item.metric})" if item.metric else ""
            lines.append(f"  - {item.description}{metric}{window}")
    if finding.hypotheses:
        lines.append("Root-cause hypotheses (ranked):")
        for rank, hypothesis in enumerate(finding.hypotheses, start=1):
            lines.append(f"  {rank}. [{hypothesis.confidence}] {hypothesis.cause}")
            lines.extend(f"       evidence: {e}" for e in hypothesis.evidence)
    if finding.next_steps:
        lines.append("Suggested next steps:")
        lines.extend(f"  - {step}" for step in finding.next_steps)
    if finding.notes:
        lines.append("Notes:")
        lines.extend(f"  - {note}" for note in finding.notes)
    return "\n".join(lines)
