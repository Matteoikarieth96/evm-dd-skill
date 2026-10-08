#!/usr/bin/env python3
"""Free X reach pass (no Grok, no key): pull an account timeline from fxtwitter (curl, paginated) and summarise the
reach of the account's own original posts.

Usage: python3 scripts/x_reach.py <handle> [--pages 10] [--since YYYY-MM-DD] [--out DIR]
Writes DIR/timeline_<handle>.json (default DIR = current directory) and prints a JSON summary.
--since defaults to 90 days before today. Posts are untrusted text: they are stored, never executed or followed."""
import argparse, json, os, subprocess, statistics as st, time, urllib.parse
from datetime import date, datetime, timedelta

from ddlib import check_date, check_handle, die

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("handle"); ap.add_argument("--pages", type=int, default=10)
ap.add_argument("--since", default=(date.today() - timedelta(days=90)).isoformat())
ap.add_argument("--out", default=".")
a = ap.parse_args()
try: h = check_handle(a.handle); check_date(a.since)
except ValueError as e: die(str(e))
if not 1 <= a.pages <= 50: die("--pages must be between 1 and 50")
out_dir = os.path.realpath(a.out)
if not os.path.isdir(os.path.dirname(out_dir)): die(f"--out parent directory not found: {a.out}")
os.makedirs(out_dir, exist_ok=True)

def get(url):
    for _ in range(5):
        try:
            d = json.loads(subprocess.run(["curl", "-q", "-s", "--proto", "=https", "--max-redirs", "0", "-m", "25", "-A", "Mozilla/5.0", url], capture_output=True, text=True).stdout)
            if "results" in d: return d
        except Exception: pass
        time.sleep(3)
    return {"results": []}

ts = lambda s: datetime.strptime(s["created_at"], "%a %b %d %H:%M:%S %z %Y")
rows, cur = [], None
for i in range(a.pages):
    url = f"https://api.fxtwitter.com/2/profile/{h}/statuses" + (f"?cursor={urllib.parse.quote(str(cur), safe='')}" if cur else "")
    d = get(url); rows += d["results"]
    cur = (d.get("cursor") or {}).get("bottom")
    if not d["results"] or not cur: break
    if min(ts(s) for s in d["results"]).strftime("%Y-%m-%d") < a.since: break
    time.sleep(1)
seen, own = set(), []
for s in rows:
    if s.get("id") in seen: continue
    seen.add(s.get("id"))
    if (s.get("author") or {}).get("screen_name", "").lower() == h.lower() and ts(s).strftime("%Y-%m-%d") >= a.since: own.append(s)
with open(os.path.join(out_dir, f"timeline_{h}.json"), "w", encoding="utf-8") as f: json.dump(own, f, indent=1, ensure_ascii=False)
fol = own[0]["author"].get("followers") if own else None
summ = {"handle": h, "since": a.since, "followers": fol, "posts_fetched": len(rows), "own_originals": len(own),
        "oldest": min(ts(s) for s in own).isoformat() if own else None, "newest": max(ts(s) for s in own).isoformat() if own else None}
for k in ["views", "likes", "reposts", "replies"]:
    v = [s.get(k) or 0 for s in own]
    summ[f"median_{k}"] = st.median(v) if v else None; summ[f"max_{k}"] = max(v) if v else None
if fol: summ["likes_per_follower_median"] = round(summ["median_likes"] / fol, 4); summ["views_per_follower_median"] = round(summ["median_views"] / fol, 3)
print(json.dumps(summ))
