#!/usr/bin/env python3
"""evm-dd page builder: scorecard.json + report.md (+ optional charts.py) -> one HTML artifact page
(tabs: 1-pager, full report) and an A4 print version of the 1-pager (optionally rendered to PDF).

Usage:
  python3 scripts/build.py <project-slug-or-dir> [--pdf]
Inputs, all inside projects/<slug>/:
  scorecard.json   categories + final rating + the "onepager" block (see templates/scorecard.template.json)
  report.md        cover + TL;DR + 3 pages + scorecard, 6 blocks separated by a line of ---
  assets/<logo>    named in onepager.logo (svg, png, jpg); omit for a monogram
  charts.py        optional: def charts(ctx) -> {"Heading text": "<figure>...</figure>"}; each figure is inserted
                   before that <h2> in the report (ctx.bar_chart and ctx.table_view help). charts.py is EXECUTED:
                   only build projects whose charts.py you wrote or reviewed, and escape every string with ctx.esc.
Outputs in projects/<slug>/site/: <slug>.html (artifact), <slug>-1pager.html, with --pdf <slug>-1pager.pdf.
The 1-pager must be exactly one A4 page; --pdf fails (exit 2) if the PDF has more.
EVM_DD_HOME overrides the workspace (default ~/evm-dd).
Security: all text is HTML-escaped; links must be absolute http(s) URLs (others are dropped); the logo must be a plain
file name inside assets/."""
import argparse, base64, html, importlib.util, json, mimetypes, os, re, shutil, subprocess, sys
from datetime import datetime
from types import SimpleNamespace

from ddlib import check_asset_name, die, project_dir, safe_url

HERE = SC = MD = OP = NAME = LOGO = None  # filled by init()

def resolve_project(arg):
    return project_dir(arg)

def init(project_dir):
    global HERE, SC, MD, OP, NAME, LOGO
    HERE = project_dir
    SC = json.load(open(os.path.join(HERE, "scorecard.json"), encoding="utf-8"))
    MD = open(os.path.join(HERE, "report.md"), encoding="utf-8").read()
    OP = SC.get("onepager") or sys.exit("scorecard.json has no 'onepager' block (see templates/scorecard.template.json)")
    NAME = SC["project"]
    LOGO = load_logo()
    mean = sum(c["score"] for c in SC["categories"]) / len(SC["categories"])
    if abs(round(mean + 1e-9, 1) - SC["final_rating"]) > 0.051:
        sys.exit(f"final_rating {SC['final_rating']} does not match the mean of the categories ({mean:.2f})")
    os.makedirs(os.path.join(HERE, "site"), exist_ok=True)

def esc(s): return html.escape(str(s), quote=True)

# ---------------------------------------------------------------- logo
def load_logo():
    name = OP.get("logo")
    if not name: return ("mono", None)
    try: check_asset_name(name)
    except ValueError as e: die(str(e))
    path = os.path.join(HERE, "assets", name)
    if not os.path.exists(path): sys.exit(f"onepager.logo not found: {path}")
    if name.lower().endswith(".svg"):
        svg = open(path, encoding="utf-8").read()
        if OP.get("logo_mono", True):
            ds = re.findall(r'<path[^>]*?\sd="([^"]+)"', svg)
            vb = re.search(r'viewBox="([^"]+)"', svg)
            if ds and vb: return ("paths", (vb.group(1), " ".join(ds)))
        return ("img", ("image/svg+xml", svg.encode("utf-8")))
    return ("img", (mimetypes.guess_type(path)[0] or "image/png", open(path, "rb").read()))

def logo(size):
    kind, data = LOGO
    if kind == "paths":
        vb, d = data
        return (f'<svg class="logo" width="{size}" height="{size}" viewBox="{vb}" role="img" aria-label="{esc(NAME)} logo">'
                f'<path d="{d}" fill="currentColor"/></svg>')
    if kind == "img":
        mime, raw = data
        return (f'<img class="logo logo-img" height="{size}" style="height:{size}px;width:auto" '
                f'src="data:{mime};base64,{base64.b64encode(raw).decode()}" alt="{esc(NAME)} logo">')
    return f'<span class="logo logo-mono" style="width:{size}px;height:{size}px;font-size:{int(size*0.55)}px" aria-hidden="true">{esc(NAME[:1].upper())}</span>'

# ---------------------------------------------------------------- score helpers
def band(score):
    if score >= 9: return ("Best in class", "good")
    if score >= 7: return ("Strong", "good")
    if score >= 5: return ("Mixed", "mixed")
    if score >= 3: return ("Weak", "weak")
    return ("Severe", "critical")

def bars(compact=False):
    rows = []
    for c in SC["categories"]:
        label, cls = band(c["score"])
        pct = c["score"] * 10
        rows.append(
            f'<div class="bar-row" data-tip="{esc(c["id"] + " " + c["name"] + ": " + str(c["score"]) + "/10 (" + c["confidence"] + " confidence). " + c["rationale"])}">'
            f'<div class="bar-name"><span class="bar-id">{esc(c["id"])}</span>{esc(c["name"])}</div>'
            f'<div class="bar-track" role="img" aria-label="{esc(c["name"])} {c["score"]} out of 10">'
            f'<div class="bar-fill {cls}" style="width:{pct}%"></div></div>'
            f'<div class="bar-val"><b>{float(c["score"]):.1f}</b><span class="bar-band">{label}</span></div>'
            f'</div>')
    axis = ('<div class="bar-axis" aria-hidden="true"><span></span><div class="bar-ticks"><i>0</i><i>5</i><i>10</i></div><span></span></div>')
    return f'<div class="bars">{"".join(rows)}{axis}</div>'

# ---------------------------------------------------------------- chart helpers for charts.py
def table_view(headers, rows):
    """Collapsed 'View as table' companion for a chart. headers: list of str; rows: list of lists (str/int)."""
    th = "".join(f'<th{" class=num" if i else ""}>{esc(h)}</th>' for i, h in enumerate(headers))
    trs = "".join("<tr>" + "".join(f'<td{" class=num" if i else ""}>{esc(c)}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    return f'<details class="tableview"><summary>View as table</summary><div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div></details>'

def bar_chart(values, labels, *, title, caption, source, aria, ymax=None, yticks=None, highlight=(), tips=None, notes=(),
              table_headers=("Label", "Value"), width=760, height=250):
    """Single-series bar chart in the house style. values: numbers; labels: x labels ('' = none); highlight: indexes;
    tips: hover text per bar; notes: [(index, 'text')] callouts above the bars. Returns a <figure> with a table view."""
    n = len(values)
    ymax = ymax or max(values) * 1.12
    if not yticks: yticks = [round(ymax * k / 3, -int(len(str(int(ymax))) - 2)) for k in range(0, 3)]
    W, H = width, height; ml, mr, mt, mb = 46, 14, 26, 32
    pw, ph = W - ml - mr, H - mt - mb
    step = pw / n; bw = max(step - 1.0, 1.5)
    fmt = lambda v: f"{v/1000:g}k" if abs(v) >= 1000 else f"{v:g}"
    out = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">']
    for v in yticks:
        y = mt + ph - ph * v / ymax
        out.append(f'<line x1="{ml}" x2="{W-mr}" y1="{y:.1f}" y2="{y:.1f}" class="grid{" base" if v == 0 else ""}"/>')
        out.append(f'<text x="{ml-8}" y="{y+4:.1f}" class="axis" text-anchor="end">{fmt(v)}</text>')
    for i, v in enumerate(values):
        h = ph * v / ymax; x = ml + i * step; y = mt + ph - h
        tip = f' data-tip="{esc(tips[i])}"' if tips else ""
        out.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{h:.2f}" rx="1" class="b{" hi" if i in highlight else ""}"{tip}/>')
        if labels[i]: out.append(f'<text x="{x:.1f}" y="{H-10}" class="axis" text-anchor="start">{esc(labels[i])}</text>')
    for i, text in notes:
        xr = ml + i * step + bw / 2
        out.append(f'<text x="{xr-8:.1f}" y="{mt-10}" class="note" text-anchor="end">{esc(text)}</text>')
        out.append(f'<line x1="{xr-6:.1f}" x2="{xr:.1f}" y1="{mt-14}" y2="{mt+2}" class="lead"/>')
    out.append("</svg>")
    table = table_view(table_headers, [[labels[i] or i + 1, f"{v:,}" if isinstance(v, int) else v] for i, v in enumerate(values)])
    return (f'<figure class="figure"><figcaption><b>{esc(title)}</b>. {esc(caption)}</figcaption>{"".join(out)}'
            f'<div class="chart-src">{esc(source)}</div>{table}</figure>')

def load_charts():
    p = os.path.join(HERE, "charts.py")
    if not os.path.exists(p): return {}
    spec = importlib.util.spec_from_file_location("project_charts", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    ctx = SimpleNamespace(dir=HERE, sc=SC, op=OP, name=NAME, esc=esc, bar_chart=bar_chart, table_view=table_view)
    return m.charts(ctx)


# ---------------------------------------------------------------- markdown subset -> html
def inline(t):
    t = esc(t)
    codes = []
    def keep(m):
        codes.append(m.group(1)); return f"\x00{len(codes)-1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', t)
    def autolink(m):
        u = m.group(0); tail = ""
        while u and u[-1] in ".,;)": tail = u[-1] + tail; u = u[:-1]
        return f'<a href="{u}" target="_blank" rel="noopener noreferrer">{u}</a>{tail}'
    t = re.sub(r'(?<![">=])https?://[^\s<]+', autolink, t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)
    return t

def md_blocks(text):
    lines = text.strip("\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip(): i += 1; continue
        m = re.match(r"^(#{1,3}) (.*)", ln)
        if m:
            lvl = len(m.group(1)); out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
            head = cells(rows[0]); body = [cells(r) for r in rows[2:]]
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f'<div class="tbl"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>'); continue
        if re.match(r"^- ", ln):
            items = []
            while i < len(lines) and re.match(r"^(- |  - )", lines[i]):
                if lines[i].startswith("  - "):
                    sub = []
                    while i < len(lines) and lines[i].startswith("  - "):
                        sub.append(inline(lines[i][4:])); i += 1
                    items[-1] += "<ul>" + "".join(f"<li>{x}</li>" for x in sub) + "</ul>"
                else:
                    items.append(inline(lines[i][2:])); i += 1
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"); continue
        if re.match(r"^\d+\. ", ln):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                items.append(inline(re.sub(r"^\d+\. ", "", lines[i]))); i += 1
            out.append("<ol>" + "".join(f"<li>{x}</li>" for x in items) + "</ol>"); continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3} |\||- |\d+\. )", lines[i]):
            para.append(lines[i]); i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


# ---------------------------------------------------------------- report
def report_html():
    blocks = re.split(r"\n---\n", MD)
    if len(blocks) != 6:
        sys.exit(f"report.md must have 6 blocks separated by ---  (cover, TL;DR, page 1, page 2, page 3, scorecard); got {len(blocks)}")
    cover_md, tldr_md, p1, p2, p3, score_md = blocks
    cover_lines = [l for l in cover_md.strip().split("\n") if not l.startswith("# ")]
    cover = md_blocks("\n".join(cover_lines))
    tldr = md_blocks(tldr_md.replace("## TL;DR", "").strip())
    def sheet(md, n, total, title):
        body = md_blocks(re.sub(r"^# .*\n", "", md.strip() + "\n", count=1))
        return (f'<article class="sheet rpt"><header class="run"><span>{esc(NAME)} due diligence</span><span>Page {n} of {total}: {esc(title)}</span></header>{body}</article>')
    s1 = sheet(p1, 1, 3, "Overview and business")
    s2 = sheet(p2, 2, 3, "Technology, legal, team")
    s3 = sheet(p3, 3, 3, "Market, traction, risks, verdict")
    score_body = md_blocks(re.sub(r"^# .*\n", "", score_md.strip() + "\n", count=1))
    s4 = (f'<article class="sheet rpt"><header class="run"><span>{esc(NAME)} due diligence</span><span>Scorecard</span></header><h1>Scorecard</h1>{bars()}{score_body}</article>')
    cover_sheet = (f'<article class="sheet rpt cover"><header class="cover-head">{logo(40)}<div><div class="eyebrow">Due diligence report, investor angle</div><h1>{esc(NAME)}</h1></div>'
                   f'<div class="rate-mini"><b>{SC["final_rating"]:.1f}</b><span>/10</span></div></header>{cover}'
                   f'<h2>TL;DR</h2>{tldr}{bars()}</article>')
    out = cover_sheet + s1 + s2 + s3 + s4
    for heading, fig in load_charts().items():
        marker = f"<h2>{inline(heading)}</h2>"
        if marker not in out:
            print(f"warning: charts.py heading not found in report, chart skipped: {heading!r}", file=sys.stderr); continue
        out = out.replace(marker, fig + marker, 1)
    return out

# ---------------------------------------------------------------- the 1-pager sheet
def onepager():
    L = lambda k: OP.get(k) or []
    if len(L("kpis")) != 6: sys.exit(f"onepager.kpis must have exactly 6 entries, has {len(L('kpis'))}")
    kpi_html = "".join(f'<div class="kpi"><div class="k">{esc(a)}</div><div class="v">{esc(b)}</div><div class="s">{inline(c)}</div></div>' for a, b, c in L("kpis"))
    facts_html = "".join(f"<tr><th>{esc(a)}</th><td>{inline(b)}</td></tr>" for a, b in L("facts"))
    peers_html = "".join(f"<tr><th>{esc(a)}</th><td>{inline(b)}</td><td>{inline(c)}</td></tr>" for a, b, c in L("peers"))
    links_html = "".join(f'<a href="{esc(safe_url(u))}" target="_blank" rel="noopener noreferrer">{esc(l)}</a>' for l, u in L("links") if safe_url(u))
    ul = lambda items: "".join(f"<li>{inline(x)}</li>" for x in items)
    verdict = OP.get("verdict_label") or SC.get("verdict", "")
    scale_note = OP.get("scale_note") or "Scale 1 to 10, equal weights. Bars: weak 3 to 4.9, mixed 5 to 6.9, strong 7 and above."
    footer = OP.get("footer") or (f'As of {SC["as_of"]}. Independent research, not affiliated with {NAME}. Not investment advice. '
                                  'Numbers marked verified in the full report were reproduced from the primary source or onchain; the rest are claimed by the team or reported by third parties. '
                                  'Rating is the simple average of 8 category scores in scorecard.json.')
    peers_block = ""
    if L("peers"):
        peers_block = (f'<h2>Peers</h2><div class="tbl"><table class="kv peers"><tbody>{peers_html}</tbody></table></div>'
                       + (f'<p class="small">{inline(OP["peers_note"])}</p>' if OP.get("peers_note") else ""))
    return f'''
<article class="sheet op" id="op-sheet">
  <header class="op-head">
    <div class="id">
      {logo(52)}
      <div>
        <div class="eyebrow">{esc(OP["category_tag"])}</div>
        <h1>{esc(NAME)}</h1>
        <p class="tag">{inline(OP["tagline"])}</p>
      </div>
    </div>
    <div class="rating" aria-label="Final rating {SC["final_rating"]} out of 10">
      <div class="r-num"><b>{SC["final_rating"]:.1f}</b><span>/10</span></div>
      <div class="r-meta">Average of 8 categories<br>Confidence: {esc(SC["average_confidence"])}</div>
      <div class="verdict"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>{esc(verdict)}</div>
    </div>
  </header>
  <p class="tldr"><b>TL;DR.</b> {inline(OP["tldr"])}</p>
  <section class="kpis" aria-label="Key numbers">{kpi_html}</section>
  <div class="op-grid">
    <section class="col">
      <h2>Scorecard</h2>
      {bars()}
      <p class="small">{inline(scale_note)}</p>
      <h2>Key facts</h2>
      <div class="tbl"><table class="kv"><tbody>{facts_html}</tbody></table></div>
    </section>
    <section class="col">
      <h2>Strengths</h2><ul class="sr plus">{ul(L("strengths"))}</ul>
      <h2>Risks</h2><ul class="sr minus">{ul(L("risks"))}</ul>
      {peers_block}
    </section>
  </div>
  <section class="verdict-box">
    <div><h2>Investor view</h2><p>{inline(OP["investor_view"])}</p></div>
    <div><h2>Would raise the rating</h2><ul>{ul(L("would_raise"))}</ul></div>
    <div><h2>Would lower it</h2><ul>{ul(L("would_lower"))}</ul></div>
  </section>
  <nav class="links" aria-label="Links">{links_html}</nav>
  <footer class="foot">{inline(footer)}</footer>
</article>'''

# ---------------------------------------------------------------- css / page shell
CSS = r'''
:root{
  /* Layout concept: an investor tearsheet. A white sheet on a cool grey ground, hairline rules, data set in mono, one blue for marks and links.
     Score bands use the fixed status colours with a text label so colour never carries meaning alone. */
  --bg:#E9ECF0; --sheet:#FFFFFF; --sheet-2:#F5F6F8; --ink:#111827; --ink-2:#434B59; --ink-3:#69717F; --rule:#D5D9E0;
  --accent:#1C5CAB; --accent-soft:#E6EEFA; --track:#E7EAEF; --bar:#9EC5F4; --bar-hi:#1C5CAB;
  --weak:#EC835A; --mixed:#FAB219; --good:#0CA30C; --critical:#D03B3B;
  --f-display:'Bricolage Grotesque','Avenir Next','Segoe UI',system-ui,sans-serif;
  --f-body:'Public Sans','Segoe UI',system-ui,-apple-system,sans-serif;
  --f-mono:'IBM Plex Mono',ui-monospace,'SF Mono',Menlo,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0C0F14; --sheet:#151922; --sheet-2:#1B202B; --ink:#F1F3F6; --ink-2:#B4BBC7; --ink-3:#8D95A3; --rule:#2B313D;
  --accent:#86B6EF; --accent-soft:#1A2740; --track:#262C38; --bar:#256ABF; --bar-hi:#86B6EF; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0C0F14; --sheet:#151922; --sheet-2:#1B202B; --ink:#F1F3F6; --ink-2:#B4BBC7; --ink-3:#8D95A3; --rule:#2B313D;
  --accent:#86B6EF; --accent-soft:#1A2740; --track:#262C38; --bar:#256ABF; --bar-hi:#86B6EF; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font:14px/1.55 var(--f-body);padding-inline:16px;padding-block:0 48px}
a{color:var(--accent);text-underline-offset:2px}
h1,h2,h3{font-family:var(--f-display);text-wrap:balance;line-height:1.15;margin:0}
.nav{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;display:flex;align-items:center;justify-content:space-between;gap:12px;
  max-width:980px;margin:0 auto;padding:10px 0;background:var(--bg)}
.nav .brand{display:flex;align-items:center;gap:10px;font-family:var(--f-display);font-weight:700;font-size:15px}
.nav .brand .logo{color:var(--ink)}
.tabs{display:flex;gap:4px;background:var(--track);padding:3px;border-radius:8px}
.tabs button{font:600 13px var(--f-body);color:var(--ink-2);background:transparent;border:0;padding:7px 14px;border-radius:6px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--sheet);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}
.tabs button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
main{max-width:980px;margin:0 auto;display:flex;flex-direction:column;gap:20px}
.sheet{background:var(--sheet);border:1px solid var(--rule);border-radius:4px;padding:32px;min-width:0}
.logo{color:var(--ink);flex:none}
.eyebrow{font:500 11px/1.3 var(--f-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3)}
.small{font-size:12px;color:var(--ink-3);margin:8px 0 0}
.num{font-family:var(--f-mono);text-align:right;font-variant-numeric:tabular-nums}

/* ---- 1-pager */
.op-head{display:flex;justify-content:space-between;gap:24px;align-items:flex-start;flex-wrap:wrap;padding-bottom:20px;border-bottom:2px solid var(--ink)}
.op-head .id{display:flex;gap:16px;align-items:center;min-width:0;flex:1 1 380px}
.op-head h1{font-size:44px;font-weight:800;letter-spacing:-.02em;margin:2px 0 4px}
.tag{margin:0;color:var(--ink-2);max-width:46ch}
.rating{display:flex;flex-direction:column;align-items:flex-end;gap:4px;text-align:right}
.r-num{display:flex;align-items:baseline;gap:4px;font-family:var(--f-display)}
.r-num b{font-size:64px;line-height:.95;font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.r-num span{font-size:20px;color:var(--ink-3);font-weight:600}
.r-meta{font:500 11px/1.4 var(--f-mono);color:var(--ink-3)}
.verdict{display:inline-flex;align-items:center;gap:7px;margin-top:4px;padding:5px 11px;border:1.5px solid var(--ink);border-radius:999px;font:700 12px var(--f-body);letter-spacing:.02em}
.tldr{margin:18px 0;font-size:15px;line-height:1.55;max-width:78ch}
.kpis{display:grid;grid-template-columns:repeat(6,1fr);border-block:1px solid var(--rule)}
.kpi{padding:12px 12px 12px 14px;border-left:1px solid var(--rule);min-width:0}
.kpi:first-child{border-left:0;padding-left:0}
.kpi .k{font:500 10.5px var(--f-mono);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3)}
.kpi .v{font:800 26px/1.15 var(--f-display);letter-spacing:-.02em;margin:3px 0 1px;font-variant-numeric:tabular-nums}
.kpi .s{font-size:11.5px;color:var(--ink-2);line-height:1.35}
.op-grid{display:grid;grid-template-columns:1.05fr 1fr;gap:28px;margin-top:22px}
.col{min-width:0}
.col h2,.verdict-box h2{font:700 12px var(--f-mono);letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3);padding-bottom:6px;margin:0 0 10px;border-bottom:1px solid var(--rule)}
.col h2:not(:first-child){margin-top:20px}
.bars{display:flex;flex-direction:column;gap:7px}
.bar-row{display:grid;grid-template-columns:minmax(120px,190px) 1fr 92px;gap:10px;align-items:center}
.bar-name{font-size:12.5px;line-height:1.25}
.bar-id{font:600 10.5px var(--f-mono);color:var(--ink-3);margin-right:6px}
.bar-track{position:relative;height:10px;background:var(--track);border-radius:2px;overflow:hidden}
.bar-track::after{content:"";position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--sheet)}
.bar-fill{position:relative;z-index:1;height:100%;border-radius:0 3px 3px 0}
.bar-fill.weak{background:var(--weak)} .bar-fill.mixed{background:var(--mixed)} .bar-fill.good{background:var(--good)} .bar-fill.critical{background:var(--critical)}
.bar-val{display:flex;align-items:baseline;gap:6px;font-variant-numeric:tabular-nums}
.bar-val b{font:700 14px var(--f-mono)}
.bar-band{font-size:11px;color:var(--ink-3)}
.bar-axis{display:grid;grid-template-columns:minmax(120px,190px) 1fr 92px;gap:10px}
.bar-ticks{display:flex;justify-content:space-between;font:500 10px var(--f-mono);color:var(--ink-3)}
.bar-ticks i{font-style:normal}
.sr{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
.sr li{position:relative;padding-left:20px;font-size:13px;line-height:1.45}
.sr li::before{position:absolute;left:0;top:0;font:700 14px/1.3 var(--f-mono)}
.sr.plus li::before{content:"+";color:var(--good)} .sr.minus li::before{content:"\2212";color:var(--critical)}
.tbl{overflow-x:auto;max-width:100%}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:6px 10px 6px 0;text-align:left;vertical-align:top;border-bottom:1px solid var(--rule)}
thead th{font:600 11px var(--f-mono);letter-spacing:.04em;text-transform:uppercase;color:var(--ink-3);border-bottom:1.5px solid var(--ink)}
.kv th{width:30%;font-weight:600;color:var(--ink-2);font-size:12.5px;padding-right:10px}
.kv td{font-size:12.5px}
.peers th{width:34%}
.verdict-box{display:grid;grid-template-columns:1.3fr 1fr 1fr;gap:24px;margin-top:22px;padding:16px 18px;background:var(--sheet-2);border:1px solid var(--rule);border-radius:3px}
.verdict-box p,.verdict-box li{font-size:12.5px;line-height:1.45;margin:0}
.verdict-box ul{margin:0;padding-left:16px;display:flex;flex-direction:column;gap:4px}
.links{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:18px;font:500 12px var(--f-mono)}
.foot{margin-top:16px;padding-top:12px;border-top:1px solid var(--rule);font-size:11px;color:var(--ink-3);line-height:1.5}

/* ---- report */
.rpt{padding:40px 44px}
.rpt h1{font-size:30px;font-weight:800;letter-spacing:-.02em;margin-bottom:14px}
.rpt h2{font-size:19px;font-weight:700;margin:28px 0 10px;padding-top:14px;border-top:1px solid var(--rule)}
.rpt h3{font-size:15px;margin:18px 0 6px}
.rpt p,.rpt li{max-width:76ch}
.rpt ul,.rpt ol{padding-left:20px;display:flex;flex-direction:column;gap:5px;margin:8px 0}
.rpt p{margin:8px 0}
.rpt code{font:12px var(--f-mono);background:var(--sheet-2);padding:1px 5px;border-radius:3px}
.rpt .tbl{margin:10px 0 14px}
.rpt table{font-size:12.5px}
.rpt td,.rpt th{padding:7px 12px 7px 0}
.run{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font:500 11px var(--f-mono);letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3);padding-bottom:10px;margin-bottom:20px;border-bottom:1px solid var(--rule)}
.cover-head{display:flex;gap:16px;align-items:center;padding-bottom:16px;margin-bottom:14px;border-bottom:2px solid var(--ink)}
.cover-head h1{font-size:46px;margin:2px 0 0}
.rate-mini{margin-left:auto;display:flex;align-items:baseline;gap:3px;font-family:var(--f-display)}
.rate-mini b{font-size:54px;font-weight:800;letter-spacing:-.03em;line-height:1}
.rate-mini span{font-size:18px;color:var(--ink-3);font-weight:600}
.cover .bars{margin-top:22px;max-width:640px}
.figure{margin:22px 0 8px}
.figure figcaption{font-size:13px;margin-bottom:8px;max-width:76ch}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart .grid{stroke:var(--rule);stroke-width:1}.chart .grid.base{stroke:var(--ink-3)}
.chart .axis{font:500 10.5px var(--f-mono);fill:var(--ink-3)}
.chart .note{font:500 11px var(--f-body);fill:var(--ink)}
.chart .lead{stroke:var(--ink-3);stroke-width:1}
.chart .b{fill:var(--bar)} .chart .b.hi{fill:var(--bar-hi)} .chart .b:hover{fill:var(--bar-hi)}
.chart-src{font-size:11px;color:var(--ink-3);margin-top:6px}
.tableview{margin-top:8px;font-size:12.5px}
.tableview summary{cursor:pointer;color:var(--accent);font-weight:600}
.tableview table{max-width:420px;margin-top:6px}
#tip{position:fixed;z-index:20;pointer-events:none;max-width:320px;padding:8px 10px;border-radius:5px;font-size:12px;line-height:1.4;background:var(--ink);color:var(--sheet);box-shadow:0 4px 14px rgba(0,0,0,.25);opacity:0;transition:opacity .08s}
#tip.on{opacity:1}

@media screen and (max-width:820px){
  .kpis{grid-template-columns:repeat(3,1fr)}
  .kpi:nth-child(4){border-left:0;padding-left:0}
  .kpi{border-bottom:1px solid var(--rule)}
  .op-grid,.verdict-box{grid-template-columns:1fr}
  .rating{align-items:flex-start;text-align:left}
}
@media screen and (max-width:560px){
  .sheet,.rpt{padding:20px 16px}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .kpi:nth-child(odd){border-left:0;padding-left:0}.kpi:nth-child(even){border-left:1px solid var(--rule);padding-left:14px}
  .kpi:nth-child(4){border-left:1px solid var(--rule);padding-left:14px}
  .op-head h1{font-size:34px}.r-num b{font-size:52px}
  .bar-row,.bar-axis{grid-template-columns:1fr 86px}
  .bar-name{grid-column:1 / -1}
  .bar-axis span:first-child{display:none}
  .cover-head{flex-wrap:wrap}.cover-head h1{font-size:36px}
  .nav .brand span{display:none}
}
@media print{
  @page{size:A4;margin:0}
  html,body{background:#fff !important;padding:0 !important}
  .nav,#tip,#view-report{display:none !important}
  main{max-width:none;margin:0}
  .sheet{border:0;border-radius:0;zoom:.72;width:calc(210mm / .72);min-height:calc(295mm / .72);padding:11mm 12mm;overflow:visible}
  .op-head{padding-bottom:14px}
  .kv th,.kv td{padding-block:4px}
  .op-head h1{font-size:40px}.r-num b{font-size:56px}
  .tldr{font-size:14px;margin:14px 0}
  .kpi{padding-block:10px}.kpi .v{font-size:24px}
  .op-grid{gap:26px;margin-top:16px}
  .bars{gap:6px}
  .verdict-box{margin-top:16px;padding:14px 16px}
  .links{margin-top:14px}
  .foot{margin-top:12px}
}
.logo-mono{display:inline-grid;place-items:center;border:2px solid currentColor;border-radius:50%;font-family:var(--f-display);font-weight:800;line-height:1}
.logo-img{background:#fff;border-radius:8px;padding:3px;max-width:160px;object-fit:contain}
#view-report:not([hidden]){display:flex;flex-direction:column;gap:20px}
[hidden]{display:none !important}
@media (prefers-reduced-motion:reduce){*{transition:none !important}}
'''


JS = r'''
(function(){
  var tip=document.getElementById('tip');
  function show(e,t){tip.textContent=t;tip.classList.add('on');var w=tip.offsetWidth,h=tip.offsetHeight;
    var x=Math.min(e.clientX+14,window.innerWidth-w-8),y=e.clientY+16;if(y+h>window.innerHeight-8)y=e.clientY-h-12;
    tip.style.left=Math.max(8,x)+'px';tip.style.top=Math.max(8,y)+'px';}
  document.addEventListener('mousemove',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');
    if(t)show(e,t.getAttribute('data-tip'));else tip.classList.remove('on');});
  document.addEventListener('click',function(e){var t=e.target.closest&&e.target.closest('[data-tip]');
    if(t&&('ontouchstart' in window))show(e,t.getAttribute('data-tip'));else if(!t)tip.classList.remove('on');});
  var views={onepager:document.getElementById('view-onepager'),report:document.getElementById('view-report')};
  var btns=document.querySelectorAll('.tabs button');
  function go(name){if(!views[name])name='onepager';
    for(var k in views)views[k].hidden=(k!==name);
    btns.forEach(function(b){b.setAttribute('aria-selected',b.dataset.view===name?'true':'false');});
    try{history.replaceState(null,'','#'+name);}catch(e){}
    window.scrollTo(0,0);}
  btns.forEach(function(b){b.addEventListener('click',function(){go(b.dataset.view);});});
  var h=(location.hash||'').replace('#','');go(h==='report'?'report':'onepager');
})();
'''



def shell_head():
    return f'''<title>{esc(NAME)} Due Diligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=IBM+Plex+Mono:wght@500;600&family=Public+Sans:wght@400;500;600;700&display=swap">
'''

def page():
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{shell_head()}<style>{CSS}</style></head><body>
<header class="nav"><div class="brand">{logo(22)}<span>{esc(NAME)} due diligence</span></div>
<div class="tabs" role="tablist"><button role="tab" data-view="onepager" aria-selected="true">1-pager</button><button role="tab" data-view="report" aria-selected="false">Full report</button></div></header>
<main>
<div id="view-onepager">{onepager()}</div>
<div id="view-report" hidden>{report_html()}</div>
</main>
<div id="tip" role="tooltip"></div>
<script>{JS}</script></body></html>'''

def print_page():
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">{shell_head()}<style>{CSS}</style></head>
<body><main><div id="view-onepager">{onepager()}</div></main></body></html>'''

def find_chrome():
    for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
              shutil.which("google-chrome"), shutil.which("chromium")):
        if c and os.path.exists(c): return c
    sys.exit("Chrome not found; needed for --pdf")

def page_count(pdf):
    if shutil.which("pdfinfo"):
        m = re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout)
        if m: return int(m.group(1))
    return len(re.findall(rb"/Type\s*/Page[^s]", open(pdf, "rb").read()))

def render_pdf(html_path, pdf_path):
    cmd = [find_chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=6000",
           f"--print-to-pdf={pdf_path}", "file://" + html_path]
    subprocess.run(cmd, capture_output=True, timeout=120)
    if not os.path.exists(pdf_path): sys.exit("PDF was not produced")
    n = page_count(pdf_path)
    print(f"pdf: {pdf_path} ({n} page{'s' if n != 1 else ''})")
    if n != 1:
        print("ERROR: the 1-pager overflows one A4 page. Shorten text (tldr, risks, facts) and rebuild.", file=sys.stderr); sys.exit(2)

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project"); ap.add_argument("--pdf", action="store_true", help="also render the A4 1-pager to PDF and require 1 page")
    a = ap.parse_args()
    init(resolve_project(a.project))
    slug = os.path.basename(HERE)
    site = os.path.join(HERE, "site")
    open(os.path.join(site, f"{slug}.html"), "w", encoding="utf-8").write(page())
    op = os.path.join(site, f"{slug}-1pager.html")
    open(op, "w", encoding="utf-8").write(print_page())
    print("built", os.path.join(site, f"{slug}.html"), os.path.getsize(os.path.join(site, f"{slug}.html")), "bytes")
    if a.pdf: render_pdf(op, os.path.join(site, f"{slug}-1pager.pdf"))

if __name__ == "__main__":
    main()
