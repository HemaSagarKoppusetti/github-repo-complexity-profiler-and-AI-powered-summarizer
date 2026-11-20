"""Self-contained HTML report renderer."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape

from app.core.exporters.report_model import ReportModel, section_content

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ model.repo_name }} repository analysis</title>
<style>
:root{color-scheme:light dark;--bg:#f8fafc;--fg:#172033;--card:#fff;--line:#cbd5e1;--accent:#2563eb}
@media(prefers-color-scheme:dark){:root{--bg:#0f172a;--fg:#e2e8f0;--card:#172033;--line:#334155;--accent:#60a5fa}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,Segoe UI,sans-serif}
.layout{display:grid;grid-template-columns:230px minmax(0,1000px);gap:28px;max-width:1320px;margin:auto;padding:28px}
nav{position:sticky;top:18px;align-self:start;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
nav a{display:block;color:var(--accent);text-decoration:none;padding:4px 0}
main{min-width:0}header,.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px;margin:0 0 18px}
h1,h2,h3{line-height:1.2}h2{border-bottom:1px solid var(--line);padding-bottom:10px}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.kpi{padding:14px;background:var(--bg);border:1px solid var(--line);border-radius:10px}
.kpi strong{display:block;font-size:1.4rem}.chart{width:100%;height:auto;margin:10px 0;border:1px solid var(--line);border-radius:8px}
figure{margin:18px 0}figcaption{font-size:.92rem}figcaption small{display:block;opacity:.8}
table{width:100%;border-collapse:collapse;display:block;overflow-x:auto}th,td{text-align:left;padding:9px;border-bottom:1px solid var(--line);vertical-align:top}
th{cursor:pointer;background:var(--bg)}details{border-bottom:1px solid var(--line);padding:10px 0}
.tier-Critical{color:#b91c1c}.tier-High{color:#ea580c}.tier-Medium{color:#a16207}.tier-Low{color:#15803d}
code{overflow-wrap:anywhere} .muted{opacity:.75}
@media(max-width:850px){.layout{grid-template-columns:1fr;padding:12px}nav{position:static}.kpis{grid-template-columns:repeat(2,1fr)}}
@media print{body{background:white;color:black}.layout{display:block;max-width:none;padding:0}nav{display:none}.card,header{break-inside:avoid;border:0;padding:12px}details>*{display:block}details>summary{list-style:none}a{color:inherit}}
</style>
</head>
<body>
<div class="layout">
<nav aria-label="Table of contents"><strong>Contents</strong>
{% for title, anchor in toc %}<a href="#{{ anchor }}">{{ title }}</a>{% endfor %}
</nav>
<main>
<header><p class="muted">GitHub Repo Complexity Profiler · {{ model.generated_at }} · Tool {{ model.tool_version }}</p>
<h1>{{ model.repo_name }}</h1><p>Analysed commit window: {{ model.analysed_window }}</p></header>
<section class="card" id="executive-summary"><h2>Executive summary</h2>
<h3>{{ sections.executive_summary.headline }}</h3>
<p><strong>Health: {{ sections.executive_summary.health_rating }}</strong> — {{ sections.executive_summary.health_rationale }}</p>
<div class="kpis">{% for name, value in sections.executive_summary.kpis.items() %}<div class="kpi"><span>{{ name }}</span><strong>{{ value }}</strong></div>{% endfor %}</div></section>
<section class="card" id="key-insights"><h2>Key insights</h2>
{% for item in sections.key_insights %}<details open><summary>{{ item.title }}</summary><ul>{% for evidence in item.evidence %}<li>{{ evidence }}</li>{% endfor %}</ul><p>{{ item.so_what }} Hypothesis: {{ item.likely_cause }} Confidence: {{ item.confidence }}.</p></details>{% else %}<p>No structured insights were returned.</p>{% endfor %}</section>
<section class="card" id="hotspots"><h2>Hotspot quadrant and ranking</h2>
{% for chart in charts if chart.name == "quadrant" %}<figure><img class="chart" src="{{ chart.data_uri }}" alt="{{ chart.title }}"><figcaption>{{ chart.caption }}<small>{{ chart.how_to_read }}</small></figcaption></figure>{% endfor %}
{% for chart in charts if chart.name in ["risk_tiers","hotspot_components"] %}<figure><img class="chart" src="{{ chart.data_uri }}" alt="{{ chart.title }}"><figcaption>{{ chart.caption }}<small>{{ chart.how_to_read }}</small></figcaption></figure>{% endfor %}
<p>Quadrant counts: {{ sections.hotspots.quadrant_counts }}</p><table id="hotspot-table"><thead><tr><th>File</th><th>Tier</th><th>Quadrant</th><th>Risk</th><th>CC</th><th>MI</th><th>Churn</th><th>LOC</th><th>Bug fixes</th></tr></thead><tbody>
{% for item in sections.hotspots.rows %}<tr><td><code>{{ item.rel_path }}</code></td><td class="tier-{{ item.tier }}">{{ item.tier }}</td><td>{{ item.quadrant }}</td><td>{{ item.risk_score }}</td><td>{{ item.max_cc }}</td><td>{{ item.mi_score if item.mi_available else "N/A" }}</td><td>{{ item.commit_count }}</td><td>{{ item.loc }}</td><td>{{ item.bug_fix_count }}</td></tr>{% else %}<tr><td colspan="9">No hotspots were scored.</td></tr>{% endfor %}
</tbody></table></section>
<section class="card" id="risks"><h2>Risks</h2>{% for item in sections.risks %}<p><strong>{{ item.severity }} · <code>{{ item.file }}</code></strong>: {{ item.why }} Blast radius: {{ item.blast_radius }} Failure mode: {{ item.failure_mode }}</p>{% else %}<p>No file-specific risks were returned.</p>{% endfor %}</section>
<section class="card" id="recommendations"><h2>Recommendations</h2><table><thead><tr><th>Priority</th><th>Action</th><th>Target</th><th>Benefit</th><th>Effort</th><th>Confidence</th></tr></thead><tbody>
{% for item in sections.recommendations %}<tr><td>{{ item.priority }}</td><td>{{ item.action }}</td><td><code>{{ item.target }}</code></td><td>{{ item.expected_benefit }}</td><td>{{ item.effort }}</td><td>{{ item.confidence }}</td></tr>{% else %}<tr><td colspan="6">No recommendations were returned.</td></tr>{% endfor %}
</tbody></table><h3>Quick wins</h3><ul>{% for item in model.report.quick_wins %}<li>{{ item }}</li>{% else %}<li>No quick wins were supplied.</li>{% endfor %}</ul></section>
<section class="card" id="roadmap"><h2>30/60/90-day roadmap</h2>{% for days, actions in roadmap %}<h3>{{ days }} days</h3><ul>{% for action in actions %}<li>{{ action }}</li>{% else %}<li>No evidence-specific action supplied.</li>{% endfor %}</ul>{% endfor %}</section>
<section class="card" id="architecture"><h2>Architecture and dependency analysis</h2><p>{{ sections.architecture_and_dependencies.architecture.summary }}</p>
<ul>{% for item in sections.architecture_and_dependencies.architecture.strengths %}<li>Strength: {{ item }}</li>{% endfor %}{% for item in sections.architecture_and_dependencies.architecture.concerns %}<li>Concern: {{ item }}</li>{% endfor %}</ul>
<p>Graph metrics: {{ sections.architecture_and_dependencies.graph_stats }}</p>
{% for chart in charts if chart.name == "dependency_graph" %}<figure><img class="chart" src="{{ chart.data_uri }}" alt="{{ chart.title }}"><figcaption>{{ chart.caption }}<small>{{ chart.how_to_read }}</small></figcaption></figure>{% endfor %}
<h3>Dependency cycles</h3><ul>{% for component in sections.architecture_and_dependencies.cycle_components %}<li>{{ component|join(" → ") }}</li>{% else %}<li>No cyclic strongly connected components were detected.</li>{% endfor %}</ul>
<h3>Hub modules</h3><ul>{% for item in sections.architecture_and_dependencies.hub_modules %}<li><code>{{ item.module }}</code>: fan-in {{ item.fan_in }}, fan-out {{ item.fan_out }}, instability {{ item.instability }}</li>{% else %}<li>No internal import hubs were detected.</li>{% endfor %}</ul></section>
<section class="card" id="ownership"><h2>Ownership and churn</h2><p>{{ sections.ownership_and_churn.stats }}</p>
{% for chart in charts if chart.name in ["ownership","commit_timeline"] %}<figure><img class="chart" src="{{ chart.data_uri }}" alt="{{ chart.title }}"><figcaption>{{ chart.caption }}<small>{{ chart.how_to_read }}</small></figcaption></figure>{% endfor %}
<h3>Temporal coupling</h3><ul>{% for pair in sections.ownership_and_churn.temporal_coupling %}<li>{{ pair.files|join(" ↔ ") }} changed together {{ pair.cochange_count }} times.</li>{% else %}<li>No temporal coupling pairs exceeded the reporting threshold.</li>{% endfor %}</ul>
<h3>Most changed files</h3><ul>{% for item in sections.ownership_and_churn.top_files %}<li><code>{{ item.rel_path }}</code>: {{ item.commit_count }} commits, {{ item.lines_added }} added, {{ item.lines_deleted }} deleted.</li>{% else %}<li>No file-level history was available.</li>{% endfor %}</ul></section>
<section class="card" id="testing"><h2>Testing focus</h2><ul>{% for item in sections.testing_focus %}<li><code>{{ item.file_or_module }}</code>: {{ item.reason }}</li>{% else %}<li>No testing focus was returned.</li>{% endfor %}</ul>
{% for chart in charts if chart.name in ["cc_ranks","maintainability","language_roles"] %}<figure><img class="chart" src="{{ chart.data_uri }}" alt="{{ chart.title }}"><figcaption>{{ chart.caption }}<small>{{ chart.how_to_read }}</small></figcaption></figure>{% endfor %}</section>
<section class="card" id="quality"><h2>Data quality and limitations</h2><ul>{% for item in sections.data_quality_and_limitations.diagnostics %}<li>{{ item.severity }} · {{ item.stage }}{% if item.file %} · <code>{{ item.file }}</code>{% endif %}: {{ item.message }}</li>{% else %}<li>No diagnostics were recorded.</li>{% endfor %}{% for item in sections.data_quality_and_limitations.limitations %}<li>Limitation: {{ item }}</li>{% endfor %}</ul></section>
<section class="card" id="appendix"><h2>Appendix: formula and methodology</h2><p>{{ sections.appendix.risk_formula }}</p><p>Weights: {{ sections.appendix.risk_weights }}</p><p>Tier thresholds: {{ sections.appendix.tier_thresholds }}</p><p>{{ sections.appendix.methodology }}</p></section>
</main></div>
<script>
document.querySelectorAll("th").forEach((header,index)=>header.addEventListener("click",()=>{const table=header.closest("table");if(!table||table.id!=="hotspot-table")return;const body=table.tBodies[0];const rows=[...body.rows];rows.sort((a,b)=>a.cells[index].innerText.localeCompare(b.cells[index].innerText,undefined,{numeric:true}));rows.forEach(row=>body.appendChild(row));}));
</script>
</body></html>"""

TOC = [
    ("Executive summary", "executive-summary"),
    ("Key insights", "key-insights"),
    ("Hotspots", "hotspots"),
    ("Risks", "risks"),
    ("Recommendations", "recommendations"),
    ("Roadmap", "roadmap"),
    ("Architecture and dependencies", "architecture"),
    ("Ownership and churn", "ownership"),
    ("Testing focus", "testing"),
    ("Data quality and limitations", "quality"),
    ("Appendix", "appendix"),
]


def render_html(model: ReportModel, output_path: Path) -> Path:
    """Write a single HTML file with inline styles, scripts, and data-URI charts."""
    sections = section_content(model)
    charts = [
        {
            "name": chart.name,
            "title": chart.title,
            "caption": chart.caption,
            "how_to_read": chart.how_to_read,
            "data_uri": "data:image/png;base64," + base64.b64encode(chart.png_bytes).decode("ascii"),
        }
        for chart in model.charts
    ]
    context: dict[str, Any] = {
        "model": model,
        "sections": sections,
        "charts": charts,
        "toc": TOC,
        "roadmap": [
            ("30", model.report.roadmap.days_30),
            ("60", model.report.roadmap.days_60),
            ("90", model.report.roadmap.days_90),
        ],
    }
    template = Environment(autoescape=select_autoescape(default=True)).from_string(HTML_TEMPLATE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_html = template.render(**context)
    rendered_html = re.sub(
        r"https?://[^\s\"'<>]+",
        "[external URL omitted]",
        rendered_html,
        flags=re.IGNORECASE,
    )
    output_path.write_text(rendered_html, encoding="utf-8")
    return output_path
