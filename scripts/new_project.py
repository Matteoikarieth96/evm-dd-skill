#!/usr/bin/env python3
"""Scaffold a new DD project in the workspace.
Usage: python3 scripts/new_project.py <slug> "<Name>" <https-url> [--link label=https-url ...]
Creates $EVM_DD_HOME/projects/<slug>/{sources,assets}, scorecard.json and report.md from templates, sources/00-links.md.
The slug must be lowercase letters, digits and hyphens; URLs must be http(s)."""
import argparse, os, sys
from datetime import date
from ddlib import check_slug, die, home, safe_url

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("slug"); ap.add_argument("name"); ap.add_argument("url")
ap.add_argument("--link", action="append", default=[], help="extra link as label=url (http/https only)")
a = ap.parse_args()

try: check_slug(a.slug)
except ValueError as e: die(str(e))
name = " ".join(a.name.split())
if not name or len(name) > 80 or any(c in name for c in "<>{}`"): die(f"invalid project name {a.name!r}: 1 to 80 characters, no <>{{}}`")
url = safe_url(a.url) or die(f"invalid url {a.url!r}: absolute http(s) URL required")
links = []
for l in a.link:
    label, _, u = l.partition("=")
    label = " ".join(label.split())
    if not label or len(label) > 40 or any(c in label for c in "<>{}`[]"): die(f"invalid link label in {l!r}")
    links.append((label, safe_url(u) or die(f"invalid link url in {l!r}: absolute http(s) URL required")))

HOME = home()
if not os.path.isdir(HOME): die(f"workspace {HOME} does not exist: create it (or set EVM_DD_HOME) after asking the user where it should live")
P = os.path.join(HOME, "projects", a.slug)
if os.path.exists(os.path.join(P, "scorecard.json")): die(f"{P} already has a scorecard.json; refusing to overwrite")
os.makedirs(os.path.join(P, "sources"), exist_ok=True); os.makedirs(os.path.join(P, "assets"), exist_ok=True)
today = date.today().isoformat()
for t, out in (("scorecard.template.json", "scorecard.json"), ("report.template.md", "report.md")):
    s = open(os.path.join(SKILL, "templates", t), encoding="utf-8").read()
    # values are JSON-safe: name has no quotes issues for the template because we escape backslashes and quotes
    jname = name.replace("\\", "\\\\").replace('"', '\\"') if t.endswith(".json") else name
    for k, v in (("{{NAME}}", jname), ("{{URL}}", url), ("{{DATE}}", today), ("{{SLUG}}", a.slug)): s = s.replace(k, v)
    open(os.path.join(P, out), "w", encoding="utf-8").write(s)
extra = "\n".join(f"- {label}: {u}" for label, u in links)
open(os.path.join(P, "sources", "00-links.md"), "w", encoding="utf-8").write(
    f"# Links and official channels: {name}\nAs of: {today}\n\n## Given by the user\n- Website: {url}\n{extra}\n\n"
    "## Discovered (official, identity confirmed how)\n- docs:\n- GitHub:\n- X:\n- Discord / Telegram:\n- Explorer / contracts:\n- Audits:\n- Legal pages (ToS, privacy):\n\n"
    "## Not official / impersonators seen\n-\n")
print("created", P)
if not os.path.exists(os.path.join(HOME, ".env")): print("note: no .env in the workspace; the paid X pass needs XAI_API_KEY there (the free x_reach.py pass does not)")
