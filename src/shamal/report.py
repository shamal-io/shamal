"""Report rendering (spec: reporting).

Markdown stays small enough for a PR comment; HTML is a single
self-contained file (inline CSS, inline SVG chart, zero external assets);
report_data() is the stable machine-readable schema.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, select_autoescape

from shamal.finding import Finding
from shamal.results import RunResult, SeriesPoint

MARKDOWN_BUDGET_BYTES = 4000
SCHEMA_VERSION = 1


def _verdict(result: RunResult) -> str:
    if result.passed is True:
        return "passed"
    if result.passed is False:
        return "failed"
    return "unknown"


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------


def render_markdown(
    result: RunResult, finding: Finding | None, html_path: str | None = None
) -> str:
    verdict = _verdict(result)
    scenario = result.meta.scenario or "load test"
    lines: list[str] = [f"## {verdict.upper()}: {scenario}"]

    failed = [t for t in result.thresholds if not t.passed]
    passed = [t for t in result.thresholds if t.passed]
    if failed:
        lines.append("")
        lines.append("**Failed thresholds**")
        lines.append("")
        lines.append("| Metric | Threshold |")
        lines.append("|---|---|")
        lines.extend(f"| {t.metric} | `{t.expression}` |" for t in failed)
    if passed:
        lines.append("")
        lines.append(
            "Passed thresholds: "
            + ", ".join(f"`{t.metric} {t.expression}`" for t in passed)
        )

    lines.append("")
    lines.append("**Key metrics**")
    lines.append("")
    lines.append("| p95 | avg | max | requests | error rate | peak VUs |")
    lines.append("|---|---|---|---|---|---|")
    summary = result.summary
    lines.append(
        f"| {_ms(summary.latency_p95)} | {_ms(summary.latency_avg)} "
        f"| {_ms(summary.latency_max)} | {summary.http_reqs_count or '-'} "
        f"| {_rate(summary.failed_rate)} | {summary.vus_max or '-'} |"
    )

    if finding is not None:
        lines.append("")
        lines.append(f"**Investigation**: {finding.symptom}")
        for hypothesis in finding.hypotheses[:2]:
            lines.append(f"- ({hypothesis.confidence}) {hypothesis.cause}")
        lines.extend(f"- Next: {step}" for step in finding.next_steps[:2])
        if not finding.conclusive:
            lines.append("- Note: investigation was inconclusive; partial findings only.")

    if html_path:
        lines.append("")
        lines.append(f"Full report: {html_path}")

    return _truncate("\n".join(lines), MARKDOWN_BUDGET_BYTES)


def _truncate(text: str, budget: int) -> str:
    encoded = text.encode()
    if len(encoded) <= budget:
        return text
    return encoded[: budget - 16].decode(errors="ignore") + "\n...(truncated)"


def _ms(value: float | None) -> str:
    return f"{value:.0f}ms" if value is not None else "-"


def _rate(value: float | None) -> str:
    return f"{value * 100:.2f}%" if value is not None else "-"


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

_HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shamal report: {{ scenario }}</title>
<style>
  :root { --bg: #0f1115; --panel: #171a21; --text: #e6e8ee; --muted: #9aa3b2;
          --ok: #3fb37f; --fail: #e05d5d; --accent: #6ea8fe; --border: #262b36; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 2rem; background: var(--bg); color: var(--text);
         font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }
  .wrap { max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.3rem; margin: 0 0 1rem; }
  .badge { display: inline-block; padding: .2rem .7rem; border-radius: 999px;
           font-weight: 700; font-size: .85rem; }
  .badge.passed { background: rgba(63,179,127,.15); color: var(--ok); }
  .badge.failed { background: rgba(224,93,93,.15); color: var(--fail); }
  .badge.unknown { background: rgba(154,163,178,.15); color: var(--muted); }
  section { background: var(--panel); border: 1px solid var(--border);
            border-radius: 10px; padding: 1rem 1.25rem; margin: 1rem 0; }
  h2 { font-size: 1rem; margin: 0 0 .75rem; color: var(--accent); }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  th, td { text-align: left; padding: .4rem .5rem; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; }
  .fail-row { color: var(--fail); }
  .muted { color: var(--muted); }
  .hyp { margin: .35rem 0; }
  .conf { font-size: .75rem; padding: .1rem .45rem; border-radius: 999px;
          border: 1px solid var(--border); color: var(--muted); margin-right: .4rem; }
  svg { width: 100%; height: auto; display: block; }
  .legend { font-size: .8rem; color: var(--muted); }
  .legend b.lat { color: var(--accent); } .legend b.vus { color: var(--ok); }
</style>
</head>
<body>
<div class="wrap">
  <h1>Shamal load test report
    <span class="badge {{ verdict }}">{{ verdict | upper }}</span></h1>
  <div class="muted">{{ scenario }}{% if k6_version %} - k6 v{{ k6_version }}{% endif %}
    {% if duration %} - {{ duration }}s{% endif %}</div>

  {% if thresholds %}
  <section>
    <h2>Thresholds</h2>
    <table>
      <tr><th>Metric</th><th>Threshold</th><th>Result</th></tr>
      {% for t in thresholds %}
      <tr class="{{ '' if t.passed else 'fail-row' }}">
        <td>{{ t.metric }}</td><td>{{ t.expression }}</td>
        <td>{{ 'passed' if t.passed else 'FAILED' }}</td></tr>
      {% endfor %}
    </table>
  </section>
  {% endif %}

  <section>
    <h2>Key metrics</h2>
    <table>
      <tr><th>p95</th><th>avg</th><th>max</th><th>requests</th>
          <th>error rate</th><th>peak VUs</th></tr>
      <tr><td>{{ p95 }}</td><td>{{ avg }}</td><td>{{ max }}</td>
          <td>{{ reqs }}</td><td>{{ err }}</td><td>{{ vus }}</td></tr>
    </table>
  </section>

  {% if chart %}
  <section>
    <h2>Latency vs load</h2>
    {{ chart | safe }}
    <div class="legend"><b class="lat">p95 latency</b> - <b class="vus">VUs</b></div>
  </section>
  {% endif %}

  {% if finding %}
  <section>
    <h2>Investigation</h2>
    <p><strong>{{ finding.symptom }}</strong></p>
    {% if not finding.conclusive %}
      <p class="muted">Inconclusive: partial findings only.</p>{% endif %}
    {% for h in finding.hypotheses %}
      <div class="hyp"><span class="conf">{{ h.confidence }}</span>{{ h.cause }}</div>
    {% endfor %}
    {% if finding.evidence %}
    <table>
      <tr><th>Evidence</th><th>Metric</th><th>Window</th></tr>
      {% for e in finding.evidence %}
      <tr><td>{{ e.description }}</td><td>{{ e.metric or '-' }}</td>
          <td>{% if e.window_start_s is not none %}{{ e.window_start_s|int }}s-
            {{- e.window_end_s|int }}s{% else %}-{% endif %}</td></tr>
      {% endfor %}
    </table>
    {% endif %}
    {% if finding.next_steps %}
      <p><strong>Next steps</strong></p>
      <ul>{% for s in finding.next_steps %}<li>{{ s }}</li>{% endfor %}</ul>
    {% endif %}
    {% if finding.notes %}
      <p class="muted">{% for n in finding.notes %}{{ n }}<br>{% endfor %}</p>
    {% endif %}
  </section>
  {% endif %}

  {% if errors %}
  <section>
    <h2>Error clusters</h2>
    <table>
      <tr><th>Status</th><th>URL</th><th>Error</th><th>Count</th><th>First seen</th></tr>
      {% for e in errors %}
      <tr><td>{{ e.status or '-' }}</td><td>{{ e.url or '-' }}</td>
          <td>{{ e.error or '-' }}</td><td>{{ e.count }}</td>
          <td>{{ e.first_t|int }}s</td></tr>
      {% endfor %}
    </table>
  </section>
  {% endif %}

  <p class="muted">Generated by Shamal - agentic performance testing.</p>
</div>
</body>
</html>
"""

_env = Environment(autoescape=select_autoescape(["html"]))


def render_html(result: RunResult, finding: Finding | None) -> str:
    summary = result.summary
    template = _env.from_string(_HTML_TEMPLATE)
    return template.render(
        scenario=result.meta.scenario or "load test",
        verdict=_verdict(result),
        k6_version=result.meta.k6_version,
        duration=int(result.meta.duration_s) if result.meta.duration_s else None,
        thresholds=result.thresholds,
        p95=_ms(summary.latency_p95),
        avg=_ms(summary.latency_avg),
        max=_ms(summary.latency_max),
        reqs=summary.http_reqs_count or "-",
        err=_rate(summary.failed_rate),
        vus=summary.vus_max or "-",
        chart=_series_svg(result.series),
        finding=finding,
        errors=result.errors,
    )


def _series_svg(series: list[SeriesPoint], width: int = 840, height: int = 220) -> str | None:
    points = [p for p in series if p.p95 is not None]
    if len(points) < 2:
        return None
    pad = 10
    t_min, t_max = points[0].t, points[-1].t
    t_span = (t_max - t_min) or 1.0
    p95_max = max(p.p95 for p in points if p.p95 is not None) or 1.0
    vus_values = [p.vus for p in points if p.vus is not None]
    vus_max = max(vus_values) if vus_values else None

    def x(t: float) -> float:
        return pad + (t - t_min) / t_span * (width - 2 * pad)

    def y(value: float, maximum: float) -> float:
        return height - pad - (value / maximum) * (height - 2 * pad)

    latency_pts = " ".join(
        f"{x(p.t):.1f},{y(p.p95, p95_max):.1f}" for p in points if p.p95 is not None
    )
    svg = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="p95 latency and VUs over time">',
        f'<polyline fill="none" stroke="#6ea8fe" stroke-width="2" points="{latency_pts}"/>',
    ]
    if vus_max:
        vus_pts = " ".join(
            f"{x(p.t):.1f},{y(float(p.vus), float(vus_max)):.1f}"
            for p in points
            if p.vus is not None
        )
        svg.append(
            f'<polyline fill="none" stroke="#3fb37f" stroke-width="1.5" '
            f'stroke-dasharray="4 3" points="{vus_pts}"/>'
        )
    svg.append("</svg>")
    return "".join(svg)


# --------------------------------------------------------------------------
# Machine-readable
# --------------------------------------------------------------------------


def report_data(result: RunResult, finding: Finding | None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "verdict": _verdict(result),
        "meta": result.meta.model_dump(),
        "summary": result.summary.model_dump(),
        "thresholds": [t.model_dump() for t in result.thresholds],
        "error_clusters": [e.model_dump() for e in result.errors],
        "series_point_count": len(result.series),
        "finding": finding.model_dump() if finding is not None else None,
    }
