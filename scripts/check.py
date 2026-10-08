#!/usr/bin/env python3
"""evm-dd QA lint for a project (mechanical part of the QA checklist, DD-PROCESS section 6).
Usage: python3 scripts/check.py <project-slug-or-dir>
Exit 0 = no errors (warnings may remain), 1 = errors. Judgement items (sources really back each number,
contracts opened on the explorer, adversarial pass done) stay manual."""
import json, os, re, sys
from ddlib import project_dir, read_asset, safe_url
arg = sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__)
P = project_dir(arg)
errors, warns = [], []
err = lambda m: errors.append(m); warn = lambda m: warns.append(m)
def read(p):
    try: return open(os.path.join(P, p), encoding="utf-8").read()
    except FileNotFoundError: err(f"missing file: {p}"); return ""

sc_raw = read("scorecard.json"); md = read("report.md")
sc = json.loads(sc_raw) if sc_raw else {}
cats = sc.get("categories", [])
if len(cats) != 8: err(f"expected 8 categories, found {len(cats)}")
ids = [c.get("id") for c in cats]
if ids != [f"M{i}" for i in range(1, 9)]: err(f"category ids must be M1..M8 in order, got {ids}")
for c in cats:
    s = c.get("score"); conf = str(c.get("confidence", ""))
    if not isinstance(s, (int, float)) or not 1 <= s <= 10: err(f"{c.get('id')}: score {s} outside 1-10")
    if conf.lower().startswith("low") and isinstance(s, (int, float)) and s > 7: err(f"{c.get('id')}: Low confidence cannot score above 7 (got {s})")
    if not c.get("rationale"): err(f"{c.get('id')}: rationale missing")
if cats and all(isinstance(c.get("score"), (int, float)) for c in cats):
    mean = sum(c["score"] for c in cats) / len(cats)
    if abs(round(mean + 1e-9, 1) - sc.get("final_rating", -1)) > 0.051: err(f"final_rating {sc.get('final_rating')} != mean {mean:.2f}")
m8 = next((c for c in cats if c.get("id") == "M8"), {})
if m8.get("sub_scores") and all(isinstance(v, (int, float)) for v in m8["sub_scores"].values()):
    sub = list(m8["sub_scores"].values())
    if abs(sum(sub) / len(sub) - m8["score"]) > 0.26: warn(f"M8 score {m8['score']} is not the mean of its sub_scores ({sum(sub)/len(sub):.2f})")
else: warn("M8 has no sub_scores (reach, endorsement_quality, sentiment, authenticity)")
if not sc.get("as_of"): err("scorecard.as_of missing")
if not sc.get("caps_applied") and sc.get("caps_applied") != []: warn("caps_applied not recorded (use [] when none)")

op = sc.get("onepager") or {}
if not op: err("scorecard.onepager block missing")
for k in ("category_tag", "tagline", "tldr", "investor_view", "verdict_label"):
    if not op.get(k): err(f"onepager.{k} missing")
if len(op.get("kpis", [])) != 6: err(f"onepager.kpis must have 6 entries, has {len(op.get('kpis', []))}")
for k in ("strengths", "risks", "would_raise", "would_lower", "facts", "links"):
    if not op.get(k): err(f"onepager.{k} empty")
if not op.get("peers"): warn("onepager.peers empty (peer snapshot is part of the 1-pager spec)")
if op.get("logo"):
    try: read_asset(os.path.join(P, "assets"), op["logo"])
    except (ValueError, OSError) as e: err(f"onepager.logo: {e}")
if not op.get("logo"): warn("no logo set: the page will show a monogram (QA wants the official logo)")
for item in op.get("links", []):
    if len(item) != 2 or not safe_url(item[1]): err(f"onepager.links: {item!r} is not a [label, http(s) url] pair (it would be dropped from the page)")

# text hygiene: no em/en dashes, no unfilled placeholders
for name, text in (("report.md", md), ("scorecard.json", sc_raw)):
    for ch, label in (("\u2014", "em dash"), ("\u2013", "en dash")):
        n = text.count(ch)
        if n: err(f"{name}: {n} {label}(s); the house style uses none")
    for ph in ("TODO", "TBD", "FIXME", "<<", "{{"):
        if ph in text: err(f"{name}: unfilled placeholder {ph!r}")
if len(re.split(r"\n---\n", md)) != 6: err("report.md must have 6 blocks separated by ---")
for pat in (r"\*\*Final rating: ([\d.]+) / 10", ):
    m = re.search(pat, md)
    if m and abs(float(m.group(1)) - sc.get("final_rating", -1)) > 0.001: err(f"report.md rating {m.group(1)} != scorecard {sc.get('final_rating')}")
    if not m: warn("report.md cover line '**Final rating: X / 10**' not found")
for word in ("revolutionary", "game-changing", "game changing", "cutting-edge", "best-in-class", "world-class", "disrupt"):
    if word in md.lower(): warn(f"report.md: marketing wording {word!r}")

# evidence files
src = os.path.join(P, "sources")
needed = ["01-tech-security.md", "02-legal-team.md", "03-business-traction-token.md", "04-market-competition-community.md",
          "05-peers-relative-valuation.md", "06-x-sentiment.md", "09-crosscheck.md"]
for f in needed:
    p = os.path.join(src, f)
    if not os.path.exists(p): err(f"sources/{f} missing"); continue
    t = open(p, encoding="utf-8").read()
    if not re.search(r"As of:?\s*\**\s*\d{4}-\d{2}-\d{2}", t): warn(f"sources/{f}: no 'As of: YYYY-MM-DD' line")
    if "http" not in t: warn(f"sources/{f}: no URL at all, evidence needs sources")
if not os.path.exists(os.path.join(src, "00-links.md")): warn("sources/00-links.md missing")
xs = os.path.join(src, "x-sentiment", "metrics_final.json")
if not os.path.exists(xs): warn("sources/x-sentiment/metrics_final.json missing (X sentiment not run or not finalised)")
if not os.path.exists(os.path.join(P, "site", os.path.basename(P.rstrip('/')) + "-1pager.pdf")): warn("site/<slug>-1pager.pdf not built yet (build.py --pdf)")

for w in warns: print("WARN ", w)
for e in errors: print("ERROR", e)
print(f"{len(errors)} error(s), {len(warns)} warning(s) for {os.path.basename(P.rstrip('/'))}")
sys.exit(1 if errors else 0)
