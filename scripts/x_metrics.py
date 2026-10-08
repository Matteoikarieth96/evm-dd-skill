#!/usr/bin/env python3
"""Post-process x_sentiment output into corrected, auditable metrics.
- roundup posts (the chain's weekly 'This Week on' articles) are inclusion signals, not attributable engagement
- incentivised posts (campaign / giveaway / referral / paid-in-tickets) are separated from organic ones
Usage: python3 scripts/x_metrics.py --project <slug> --handle <handle> --insiders a,b --endorsers c,d [--roundup-authors e] --today YYYY-MM-DD"""
import argparse, json, os, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ddlib import check_date, check_handle, check_handles, check_slug, die, home
ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True); ap.add_argument("--handle", required=True)
ap.add_argument("--roundup-authors", default="", help="chain/ecosystem accounts whose weekly roundup articles are inclusion signals, not engagement")
ap.add_argument("--insiders", default="", help="csv of founder/team/employee handles: excluded from third-party counts and reported separately")
ap.add_argument("--endorsers", default="", help="csv of key amplifier handles to summarise individually")
ap.add_argument("--incentive-regex", default=r"kaito|giveaway|giving away|referral|ref=|paid in|rewards? hub|quest|airdrop|campaign|winners? (are|here)|whitelist|free (ticket|mint|spin)")
ap.add_argument("--today", required=True)
a = ap.parse_args()
try:
    check_slug(a.project); a.handle = check_handle(a.handle); check_date(a.today)
    check_handles(a.insiders); check_handles(a.endorsers); check_handles(a.roundup_authors)
except ValueError as e:
    die(str(e))
root = os.path.join(home(), "projects", a.project, "sources", "x-sentiment")
V = json.load(open(f"{root}/posts_verified.json")); own = json.load(open(f"{root}/own_timeline_90d.json"))
# fxtwitter timelines include reposts of other authors: keep originals only
_au = lambda p: ((p.get("author") or {}).get("screen_name") if isinstance(p.get("author"), dict) else (p.get("author") or "")).lower().lstrip("@")
own = [p for p in own if _au(p) == a.handle.lower().lstrip("@")]
today = datetime.strptime(a.today, "%Y-%m-%d"); t30 = int((today - timedelta(days=30)).timestamp())
inc = re.compile(a.incentive_regex, re.I); roundup = {h.lower() for h in a.roundup_authors.split(",")}
eng = lambda p: p["likes"] + p["reposts"] + p["quotes"] + p["replies"]
tier = lambda f: ">500k" if f >= 500_000 else "50k-500k" if f >= 50_000 else "10k-50k" if f >= 10_000 else "1k-10k" if f >= 1_000 else "<1k"
insiders = {h.strip().lstrip("@").lower() for h in a.insiders.split(",") if h.strip()}
third = [p for p in V if (p["author"] or "").lower().lstrip("@") != a.handle.lower() and (p["author"] or "").lower().lstrip("@") not in insiders]
insider_posts = [p for p in V if (p["author"] or "").lower().lstrip("@") in insiders]
for p in third:
    p["roundup"] = (p["author"] or "").lower() in roundup and (not p["text"].strip() or p["text"].strip().startswith("https://x.com/i/article"))
    p["incentivised"] = bool(inc.search(p["text"] or "")) or p["stance"] == "giveaway-shill"
core = [p for p in third if not p["roundup"]]
core30 = [p for p in core if (p["ts"] or 0) >= t30]
organic = [p for p in core if not p["incentivised"]]
def stance(ps):
    c = Counter(p["stance"] for p in ps); n = len(ps) or 1
    return {"n": len(ps), **{k: f"{v} ({100*v/n:.0f}%)" for k, v in c.most_common()}}
def tiers(ps):
    te = sum(eng(p) for p in ps) or 1; d = defaultdict(lambda: [0, 0])
    for p in ps: d[tier(p["followers"])][0] += 1; d[tier(p["followers"])][1] += eng(p)
    return {k: {"posts": v[0], "engagement": v[1], "share_pct": round(100 * v[1] / te, 1)} for k, v in sorted(d.items(), key=lambda x: -x[1][1])}
byauth = defaultdict(lambda: {"posts": 0, "engagement": 0, "followers": 0})
for p in core:
    b = byauth[p["author"]]; b["posts"] += 1; b["engagement"] += eng(p); b["followers"] = p["followers"]
weeks = Counter()
for p in core:
    if p["ts"]: weeks[datetime.fromtimestamp(p["ts"]).strftime("%Y-W%W")] += 1
ov = [p.get("views") or 0 for p in own]; ol = [p.get("likes") or 0 for p in own]; orp = [(p.get("reposts") or 0) for p in own]
med = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0
def endorser(h):
    ps = [p for p in core if (p["author"] or "").lower().lstrip("@") == h.lower().lstrip("@")]
    return {"posts_90d": len(ps), "engagement_total": sum(eng(p) for p in ps), "top": sorted([{"url": p["url"], "date": p["created_at"], "likes": p["likes"], "reposts": p["reposts"], "quotes": p["quotes"], "views": p["views"], "text": p["text"][:140]} for p in ps], key=lambda x: -(x["views"] or 0))[:3]}
base_rounds = [p for p in third if p["roundup"]]
m = {
 "as_of": a.today, "sample": {"third_party_verified": len(third), "insider_excluded": len(insider_posts), "excluded_roundups": len(base_rounds), "core": len(core), "core_30d": len(core30), "organic_only": len(organic)},
 "stance_core_30d": stance(core30), "stance_core_90d": stance(core), "stance_organic_90d": stance(organic),
 "incentivised_share_core_90d_pct": round(100 * sum(p["incentivised"] for p in core) / len(core), 1),
 "incentivised_share_engagement_pct": round(100 * sum(eng(p) for p in core if p["incentivised"]) / (sum(eng(p) for p in core) or 1), 1),
 "engagement_tier_core_all": tiers(core), "engagement_tier_core_organic": tiers(organic),
 "top_authors_by_engagement": sorted(([k, v] for k, v in byauth.items()), key=lambda x: -x[1]["engagement"])[:12],
 "weekly_core_posts": dict(sorted(weeks.items())),
 "base_roundups": [{"url": p["url"], "date": p["created_at"], "likes": p["likes"], "reposts": p["reposts"], "views": p["views"]} for p in base_rounds],
 "endorsers": {h.strip().lstrip("@"): endorser(h) for h in a.endorsers.split(",") if h.strip()},
 "insider_posts_90d": {"n": len(insider_posts), "authors": dict(Counter(p["author"] for p in insider_posts)), "engagement_total": sum(eng(p) for p in insider_posts)},
 "own_account_90d": {"posts": len(own), "median_views": med(ov), "median_likes": med(ol), "median_reposts": med(orp), "max_views": max(ov or [0]), "max_likes": max(ol or [0]),
                     "top3": sorted([{"url": p.get("url"), "date": p.get("created_at"), "likes": p.get("likes"), "views": p.get("views"), "text": (p.get("text") or "")[:110]} for p in own], key=lambda x: -(x["views"] or 0))[:3]},
}
json.dump(m, open(f"{root}/metrics_final.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(m, indent=1, ensure_ascii=False)[:6500])
