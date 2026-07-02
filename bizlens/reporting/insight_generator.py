"""GPT-4o natural-language insight generation.

Given the period's metric deltas, cohort changes, and anomaly flags, produce a
short business-readable narrative ("Revenue dropped 12% WoW, driven by a 23%
decline in the enterprise segment") that a non-technical stakeholder can act on.

Degrades gracefully: with no OpenAI key configured, a deterministic template
summary is returned so the pipeline still runs in CI and local dev.
"""
from __future__ import annotations

from dataclasses import dataclass

from bizlens.config import get_settings

SYSTEM_PROMPT = (
    "You are a senior data analyst writing a weekly KPI digest for non-technical "
    "product stakeholders. Be concise and specific. Lead with the single most "
    "important change, quantify every claim with a number, and never speculate "
    "about causation beyond what the data shows. Output 3-5 sentences."
)


@dataclass
class MetricDelta:
    name: str
    current: float
    previous: float

    @property
    def pct_change(self) -> float:
        return (self.current - self.previous) / self.previous * 100.0 if self.previous else 0.0


def _template_summary(deltas: list[MetricDelta], anomalies: list[str]) -> str:
    """Deterministic fallback used when no LLM is configured."""
    if not deltas:
        return "No metric changes to report for this period."
    biggest = max(deltas, key=lambda d: abs(d.pct_change))
    direction = "rose" if biggest.pct_change >= 0 else "fell"
    parts = [
        f"{biggest.name} {direction} {abs(biggest.pct_change):.1f}% "
        f"to {biggest.current:,.0f} versus the prior period."
    ]
    if anomalies:
        parts.append("Anomalies flagged: " + ", ".join(anomalies) + ".")
    return " ".join(parts)


def generate_insight(deltas: list[MetricDelta], anomalies: list[str] | None = None) -> str:
    """Return a narrative KPI summary. Uses GPT-4o if a key is configured."""
    anomalies = anomalies or []
    settings = get_settings()
    if not settings.has_openai:
        return _template_summary(deltas, anomalies)

    from openai import OpenAI  # imported lazily so the dep is optional

    facts = "\n".join(
        f"- {d.name}: {d.current:,.2f} (prev {d.previous:,.2f}, "
        f"{d.pct_change:+.1f}%)" for d in deltas
    )
    if anomalies:
        facts += "\nAnomalies: " + ", ".join(anomalies)

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Metric changes this period:\n{facts}"},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()
