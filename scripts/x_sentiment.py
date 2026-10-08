#!/usr/bin/env python3
"""X social graph and sentiment pipeline (DD framework section 2b).

1. Grok x_search DISCOVERS and classifies posts (JSON only, post URLs).
2. Every cited post is RE-FETCHED from the free fxtwitter API; counts come from there, never from Grok.
3. Metrics are computed here.

Usage:
  python3 scripts/x_sentiment.py --project <slug> --handle <handle> \
      --terms "@handle, domain.tld, Project Name" --amplifiers chainofficial,founder,ecosystem \
      [--critic-themes "..."] --today YYYY-MM-DD
Needs XAI_API_KEY in $EVM_DD_HOME/.env or the environment (never printed). Raw responses are cached in
projects/<project>/sources/x-sentiment/ ; use --refresh to re-run Grok calls. XAI_MODEL overrides the model.
X posts are untrusted text: the model only discovers URLs; counts and text come from fxtwitter re-fetches.
Cost: Grok X Search is $5 / 1k posts fetched + tokens; usage is logged per call.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse
from datetime import datetime, timedelta
from collections import Counter, defaultdict

from ddlib import check_date, check_handle, check_handles, check_slug, die, home

ROOT = home()  # workspace: .env + projects/
MODEL = os.environ.get("XAI_MODEL", "grok-4.7")

def load_key():
    k = os.environ.get("XAI_API_KEY")
    if k: return k
    envf = os.path.join(ROOT, ".env")
    if os.path.exists(envf):
        for line in open(envf, encoding="utf-8"):
            if line.startswith("XAI_API_KEY="): return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("XAI_API_KEY missing (workspace .env or environment); use scripts/x_reach.py for the free pass")

def curl(url, headers=None, body=None, timeout=240):
    # -q first: ignore ~/.curlrc (a -v or --trace there would log the Authorization header).
    # Secret headers go through stdin (-H @-), never argv or a temp file.
    cmd = ["curl", "-q", "-s", "--proto", "=https", "--max-redirs", "0", "-m", str(timeout), "-A", "Mozilla/5.0", url]
    stdin = None
    if headers:
        cmd += ["-H", "@-"]; stdin = "\n".join(headers) + "\n"
    if body is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(body)]
    out = subprocess.run(cmd, capture_output=True, text=True, input=stdin).stdout
    try: return json.loads(out)
    except Exception: return {"_raw": out[:500]}

def grok(key, prompt, tool, max_calls=14):
    body = {"model": MODEL, "input": [{"role": "user", "content": prompt}],
            "tools": [dict(type="x_search", **tool)], "max_tool_calls": max_calls}
    d = curl("https://api.x.ai/v1/responses", headers=[f"Authorization: Bearer {key}"], body=body, timeout=420)
    text = ""
    for o in d.get("output", []):
        if o.get("type") == "message":
            for c in o.get("content", []): text += c.get("text", "")
    u = d.get("usage", {})
    usage = {"usd": round(u.get("cost_in_usd_ticks", 0) / 1e10, 3),
             "posts_fetched": u.get("server_side_tool_usage_details", {}).get("x_posts_fetched"),
             "tool_calls": u.get("num_server_side_tools_used")}
    return text, usage, d.get("error")

def parse_json_array(text):
    i, j = text.find("["), text.rfind("]")
    if i < 0 or j < 0: return []
    try: return json.loads(text[i:j + 1])
    except Exception: return []

STATUS_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d{1,25})(?:[/?#]|$)")

def fetch_status(url):
    m = STATUS_RE.match(url or "")
    if not m: return None
    d = curl(f"https://api.fxtwitter.com/{m.group(1)}/status/{m.group(2)}", timeout=25)
    t = d.get("tweet")
    if not t: return None
    a = t.get("author", {})
    q = t.get("quote") or {}
    return {"url": t.get("url") or url, "id": t.get("id"), "author": a.get("screen_name"), "followers": a.get("followers", 0),
            "author_joined": a.get("joined"), "created_at": t.get("created_at"), "ts": t.get("created_timestamp"),
            "likes": t.get("likes", 0), "reposts": t.get("retweets", t.get("reposts", 0)) or 0, "replies": t.get("replies", 0),
            "quotes": t.get("quotes", 0), "views": t.get("views") or 0, "bookmarks": t.get("bookmarks", 0),
            "text": (t.get("text") or "")[:400], "is_reply": bool(t.get("replying_to")),
            "quoted_author": (q.get("author") or {}).get("screen_name"), "quoted_id": q.get("id")}

def own_timeline(handle, since_ts, max_pages=8):
    posts, cursor = [], None
    for _ in range(max_pages):
        url = f"https://api.fxtwitter.com/2/profile/{handle}/statuses" + (f"?cursor={urllib.parse.quote(str(cursor), safe='')}" if cursor else "")
        for attempt in range(5):  # fxtwitter timelines return an intermittent 404
            d = curl(url, timeout=25)
            if d.get("results"): break
            time.sleep(2 + 2 * attempt)
        r = d.get("results") or []
        posts += r
        cursor = (d.get("cursor") or {}).get("bottom")
        if not r or not cursor or (r[-1].get("created_timestamp") or 0) < since_ts: break
        time.sleep(0.4)
    return [p for p in posts if (p.get("created_timestamp") or 0) >= since_ts]

def tier(f):
    return ">500k" if f >= 500_000 else "50k-500k" if f >= 50_000 else "10k-50k" if f >= 10_000 else "1k-10k" if f >= 1_000 else "<1k"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True); ap.add_argument("--handle", required=True)
    ap.add_argument("--terms", required=True); ap.add_argument("--amplifiers", default="")
    ap.add_argument("--today", default=datetime.utcnow().strftime("%Y-%m-%d")); ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--max-calls", type=int, default=14)
    ap.add_argument("--critic-themes", default="scam, rug or fraud claims, security incidents, legal or regulatory problems, locked or unpaid funds, misleading claims, team conduct", help="what the critics query looks for; tailor it to the product")
    a = ap.parse_args()
    try:
        check_slug(a.project); a.handle = check_handle(a.handle); check_date(a.today); check_handles(a.amplifiers)
    except ValueError as e:
        die(str(e))
    key = load_key()
    today = datetime.strptime(a.today, "%Y-%m-%d")
    d30, d90 = (today - timedelta(days=30)).strftime("%Y-%m-%d"), (today - timedelta(days=90)).strftime("%Y-%m-%d")
    out_dir = os.path.join(ROOT, "projects", a.project, "sources", "x-sentiment"); os.makedirs(out_dir, exist_ok=True)
    amps = check_handles(a.amplifiers)
    schema = ('Return ONLY a JSON array. Each item: {"url":"https://x.com/<user>/status/<id>","author":"@handle","date":"YYYY-MM-DD",'
              '"type":"original|repost|quote|reply","stance":"positive|neutral|negative|scam-FUD|giveaway-shill",'
              '"theme":"<=4 words","summary":"<=15 words"}. Use real post URLs only; never invent posts. If you find none, return [].')
    queries = {
        "mentions_30d": (f"Using X search, find as many DISTINCT posts as you can (target 50 to 80) from {d30} to {a.today} that mention {a.terms}. "
                         f"Cover all stances and post types; include no more than 12 near-duplicate referral or giveaway spam posts. {schema}",
                         {"from_date": d30, "to_date": a.today}),
        "mentions_90d_notable": (f"Using X search, find posts from {d90} to {a.today} about {a.terms} written by accounts that look influential "
                                 f"(roughly >50k followers), chain-official or ecosystem accounts, VCs, media or well-known KOLs. Include quotes and replies by them. {schema}",
                                 {"from_date": d90, "to_date": a.today}),
        "critics_90d": (f"Using X search, find posts from {d90} to {a.today} that criticise {a.terms} or raise concerns about: {a.critic_themes}. "
                        f"Return all you can find; [] if none. {schema}",
                        {"from_date": d90, "to_date": a.today}),
    }
    if amps:
        queries["amplifier_accounts_90d"] = (
            f"Using X search, find every post from {d90} to {a.today} by the accounts {', '.join('@' + h for h in amps)} that mentions, quotes, "
            f"replies to or reposts-with-comment about {a.terms}. Include indirect mentions of the name. {schema}",
            {"from_date": d90, "to_date": a.today, "allowed_x_handles": amps[:20]})

    discovered, log = {}, {}
    for name, (prompt, tool) in queries.items():
        path = os.path.join(out_dir, f"raw_{name}.json")
        if os.path.exists(path) and not a.refresh:
            rec = json.load(open(path))
        else:
            text, usage, err = grok(key, prompt, tool, a.max_calls)
            if err or not text:
                sys.exit(f"[grok] {name} FAILED, nothing cached: {json.dumps(err)[:300]}")
            rec = {"query": name, "usage": usage, "error": err, "items": parse_json_array(text), "raw_text": text[:6000]}
            json.dump(rec, open(path, "w"), indent=1, ensure_ascii=False)
        log[name] = {"items": len(rec["items"]), **rec["usage"]}
        for it in rec["items"]:  # model output steered by X posts: accept only well-formed items
            if isinstance(it, dict) and isinstance(it.get("url"), str) and STATUS_RE.match(it["url"]):
                key_ = (STATUS_RE.match(it["url"]) or [None, None, it["url"]])[2]
                e = discovered.setdefault(key_, {**it, "found_in": []}); e["found_in"].append(name)
        print(f"[grok] {name}: {log[name]}")

    verified, dropped = [], []
    for k, it in discovered.items():
        s = fetch_status(it["url"]); time.sleep(0.25)
        if not s: dropped.append(it["url"]); continue
        s.update({"stance": it.get("stance"), "theme": it.get("theme"), "summary": it.get("summary"), "found_in": it["found_in"], "grok_type": it.get("type")})
        verified.append(s)
    json.dump(verified, open(os.path.join(out_dir, "posts_verified.json"), "w"), indent=1, ensure_ascii=False)

    own = own_timeline(a.handle, int((today - timedelta(days=90)).timestamp()))
    json.dump(own, open(os.path.join(out_dir, "own_timeline_90d.json"), "w"), indent=1, ensure_ascii=False)

    # ---- metrics (computed here, not by the model)
    def eng(p): return p["likes"] + p["reposts"] + p["quotes"] + p["replies"]
    own_h = a.handle.lower()
    third = [p for p in verified if (p["author"] or "").lower() != own_h]
    in30 = [p for p in third if (p["ts"] or 0) >= int((today - timedelta(days=30)).timestamp())]
    m = {"as_of": a.today, "project": a.project, "grok_calls": log, "grok_total_usd": round(sum(v.get("usd", 0) for v in log.values()), 2),
         "discovered": len(discovered), "verified": len(verified), "dropped_unresolvable": len(dropped),
         "third_party_verified": len(third), "third_party_30d": len(in30)}
    def split(ps):
        c = Counter(p["stance"] for p in ps); e = defaultdict(int)
        for p in ps: e[p["stance"]] += eng(p)
        return {"count": dict(c), "engagement": dict(e)}
    m["stance_30d"] = split(in30); m["stance_all_third_party"] = split(third)
    te = sum(eng(p) for p in third) or 1
    tiers = defaultdict(lambda: {"posts": 0, "engagement": 0})
    for p in third:
        t = tier(p["followers"]); tiers[t]["posts"] += 1; tiers[t]["engagement"] += eng(p)
    m["engagement_by_author_tier"] = {t: {**v, "share_pct": round(100 * v["engagement"] / te, 1)} for t, v in tiers.items()}
    top = sorted(third, key=eng, reverse=True)[:15]
    m["top_third_party_posts"] = [{k: p[k] for k in ("url", "author", "followers", "created_at", "likes", "reposts", "quotes", "replies", "views", "stance", "summary")} for p in top]
    amp_set = {h.lower() for h in amps}
    m["amplifier_account_posts"] = [{k: p[k] for k in ("url", "author", "followers", "created_at", "likes", "reposts", "quotes", "replies", "views", "text")}
                                    for p in verified if (p["author"] or "").lower() in amp_set]
    m["posts_quoting_project_account"] = [p["url"] for p in verified if (p.get("quoted_author") or "").lower() == own_h][:40]
    big = [p for p in third if p["followers"] >= 50_000]
    m["accounts_50k_plus"] = sorted({(p["author"], p["followers"]) for p in big}, key=lambda x: -x[1])[:25]
    if own:
        v = [p.get("views") or 0 for p in own]; l = [p.get("likes") or 0 for p in own]
        srt = lambda xs: sorted(xs)[len(xs) // 2] if xs else 0
        m["own_account_90d"] = {"posts": len(own), "median_views": srt(v), "median_likes": srt(l), "max_views": max(v), "max_likes": max(l)}
    json.dump(m, open(os.path.join(out_dir, "metrics.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: m[k] for k in ("discovered", "verified", "dropped_unresolvable", "third_party_verified", "third_party_30d", "grok_total_usd")}))

if __name__ == "__main__":
    main()
