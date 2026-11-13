"""Bluesky posts about each state's races during the election-night window (public AppView API, no auth).

Queries per race: each candidate's full name (quoted), plus "<State name> election" per state.
sort=top within [W0, W1]; up to PAGES x 100 posts per query.
Then author profiles -> naive home-state guess from bio / display name ("from" a state when detectable).
Output: data/social/bluesky_posts.parquet, data/social/bluesky_authors.parquet
"""
import json, os, re, time
import pandas as pd, requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "social")
API = "https://api.bsky.app/xrpc"
SINCE, UNTIL = "2026-11-03T16:00:00Z", "2026-11-04T20:00:00Z"
PAGES = int(os.environ.get("BSKY_PAGES", 3))
s = requests.Session()
s.headers["User-Agent"] = "research-data-collector/0.1"

STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
          "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
          "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
          "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
          "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
          "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
CITIES = {"Austin": "TX", "Houston": "TX", "Dallas": "TX", "San Antonio": "TX", "Phoenix": "AZ", "Tucson": "AZ", "Atlanta": "GA", "Detroit": "MI",
          "Chicago": "IL", "Philadelphia": "PA", "Pittsburgh": "PA", "Milwaukee": "WI", "Madison": "WI", "Minneapolis": "MN", "Denver": "CO",
          "Las Vegas": "NV", "Seattle": "WA", "Portland, OR": "OR", "Boston": "MA", "Miami": "FL", "Tampa": "FL", "Orlando": "FL", "Charlotte": "NC",
          "Raleigh": "NC", "Nashville": "TN", "Columbus": "OH", "Cleveland": "OH", "Cincinnati": "OH", "Des Moines": "IA", "Omaha": "NE",
          "Anchorage": "AK", "Jackson, MS": "MS", "New Orleans": "LA", "Brooklyn": "NY", "NYC": "NY", "Los Angeles": "CA", "San Francisco": "CA",
          "Oakland": "CA", "San Diego": "CA", "Sacramento": "CA", "Salt Lake": "UT", "Albuquerque": "NM", "Richmond, VA": "VA", "Baltimore": "MD",
          "Kansas City": "MO", "St. Louis": "MO", "Indianapolis": "IN", "Louisville": "KY", "Birmingham, AL": "AL", "Boise": "ID", "Bozeman": "MT"}


def get(path, params, tries=6):
    for i in range(tries):
        try:
            r = s.get(f"{API}/{path}", params=params, timeout=30)
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** i); continue
            if r.status_code >= 400:
                print("HTTP", r.status_code, path, str(params)[:120], flush=True); return None
            time.sleep(0.35)
            return r.json()
        except requests.RequestException as e:
            print("retry", e, flush=True); time.sleep(2 ** i)
    return None


def queries():
    mk = pd.read_parquet(os.path.join(ROOT, "data/window/kalshi/markets.parquet"))
    qs = []
    for _, m in mk.iterrows():
        st = (m.race_series if isinstance(m.get("race_series"), str) else m.series_ticker)
        mm = re.match(r"^(?:SENATEPARTY-?|SENATE)([A-Z]{2})S?$|^HOUSE([A-Z]{2})(\d+)$|^(?:GOVPARTY|KXGOV)([A-Z]{2})$", st)
        if not mm: continue
        state = mm.group(1) or mm.group(2) or mm.group(4)
        kind = "senate" if mm.group(1) else "house" if mm.group(2) else "gov"
        name = (m.yes_sub_title or "").strip()
        if not name or re.search(r"party|democrat|republican|other|independent$", name, re.I) or len(name.split()) < 2:
            continue
        qs.append({"q": f'"{name}"', "state": state, "kind": kind, "event": m.event_ticker, "candidate": name})
    for ab, nm in STATES.items():
        qs.append({"q": f"{nm} election", "state": ab, "kind": "state", "event": None, "candidate": None})
    seen, out = set(), []
    for q in qs:
        if q["q"] in seen: continue
        seen.add(q["q"]); out.append(q)
    return out


def home_match(text):
    """(state, matched phrase) from a self-written bio / display name, or (None, None)."""
    t = text or ""
    for c, ab in CITIES.items():
        m = re.search(r"\b" + re.escape(c) + r"(?:,\s*[A-Z]{2}\b)?", t)
        if m: return ab, m.group(0)
    m = re.search(r"\b[A-Z][a-zA-Z .'-]{1,24},\s*([A-Z]{2})\b", t)
    if m and m.group(1) in STATES: return m.group(1), m.group(0).strip()
    for ab, nm in STATES.items():
        m = re.search(r"\b" + re.escape(nm) + r"\b", t)
        if m and not (nm == "Washington" and re.search(r"Washington,? ?D\.?C", t)): return ab, nm
    return None, None


def home_state(text):
    return home_match(text)[0]


def main():
    os.makedirs(OUT, exist_ok=True)
    qs = queries()
    print("queries", len(qs), flush=True)
    rows = []
    for i, q in enumerate(qs):
        cur = None
        for page in range(PAGES):
            p = {"q": q["q"], "since": SINCE, "until": UNTIL, "sort": "top", "limit": 100, "lang": "en"}
            if cur: p["cursor"] = cur
            d = get("app.bsky.feed.searchPosts", p)
            if not d: break
            for post in d.get("posts", []):
                a, rec = post["author"], post.get("record", {})
                rows.append({"uri": post["uri"], "did": a["did"], "handle": a["handle"], "name": a.get("displayName"),
                             "created": rec.get("createdAt"), "indexed": post.get("indexedAt"), "text": rec.get("text", ""),
                             "likes": post.get("likeCount", 0), "reposts": post.get("repostCount", 0), "replies": post.get("replyCount", 0),
                             "q": q["q"], "state": q["state"], "kind": q["kind"], "event": q["event"], "candidate": q["candidate"]})
            cur = d.get("cursor")
            if not cur or len(d.get("posts", [])) < 100: break
        if i % 25 == 0:
            print(f"query {i}/{len(qs)} {q['q'][:40]:40s} posts so far {len(rows)}", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(OUT, "bluesky_posts.parquet"))
    print("posts", len(df), "unique", df.uri.nunique() if len(df) else 0, flush=True)
    # author profiles -> home-state guess
    dids = sorted(df.did.unique()) if len(df) else []
    prof = []
    for j in range(0, len(dids), 25):
        d = get("app.bsky.actor.getProfiles", [("actors", x) for x in dids[j:j + 25]])
        for pr in (d or {}).get("profiles", []):
            txt = " ".join(filter(None, [pr.get("displayName"), pr.get("description")]))
            prof.append({"did": pr["did"], "followers": pr.get("followersCount", 0), "bio": (pr.get("description") or "")[:300],
                         "home_state": home_state(txt)})
        if j % 2500 == 0:
            print(f"profiles {j}/{len(dids)}", flush=True)
    pd.DataFrame(prof).to_parquet(os.path.join(OUT, "bluesky_authors.parquet"))
    print("DONE authors", len(prof), "with home state", sum(1 for x in prof if x["home_state"]), flush=True)


if __name__ == "__main__":
    main()
