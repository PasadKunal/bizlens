"""Assemble the weekly digest and export to PDF / CSV."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from bizlens.reporting.insight_generator import MetricDelta, generate_insight


@dataclass
class WeeklyReport:
    period_end: date
    narrative: str
    metrics: list[MetricDelta] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "metric": m.name,
                    "current": m.current,
                    "previous": m.previous,
                    "pct_change": round(m.pct_change, 2),
                }
                for m in self.metrics
            ]
        )


def build_report(
    period_end: date, metrics: list[MetricDelta], anomalies: list[str] | None = None
) -> WeeklyReport:
    """Compose a weekly report, generating the narrative via the insight engine."""
    anomalies = anomalies or []
    narrative = generate_insight(metrics, anomalies)
    return WeeklyReport(period_end=period_end, narrative=narrative, metrics=metrics, anomalies=anomalies)


def export_csv(report: WeeklyReport, out_dir: str | Path = "data/reports") -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest_{report.period_end.isoformat()}.csv"
    report.to_dataframe().to_csv(path, index=False)
    return path


def export_pdf(report: WeeklyReport, out_dir: str | Path = "data/reports") -> Path:
    """Render the report to PDF via reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"digest_{report.period_end.isoformat()}.pdf"

    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - inch
    c.setFont("Helvetica-Bold", 18)
    c.drawString(inch, y, f"BizLens Weekly Digest — {report.period_end.isoformat()}")
    y -= 0.5 * inch
    c.setFont("Helvetica", 11)
    for line in _wrap(report.narrative, 90):
        c.drawString(inch, y, line)
        y -= 0.25 * inch
    y -= 0.25 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(inch, y, "Metrics")
    y -= 0.3 * inch
    c.setFont("Helvetica", 10)
    for m in report.metrics:
        c.drawString(inch, y, f"{m.name}: {m.current:,.0f} ({m.pct_change:+.1f}%)")
        y -= 0.22 * inch
    c.save()
    return path


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines
