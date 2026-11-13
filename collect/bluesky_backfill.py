"""Bluesky backfill Aug 1 -> Nov 12: same queries as bluesky_collect.py, one day at a time (top 100 per query per day).

Resumable: one parquet per day in data/social/bluesky_daily/YYYY-MM-DD.parquet (skipped if present).
Unauthenticated public AppView allows only the first page per query, so day-slicing is how we get coverage.
"""
import os, sys, time
from datetime import date, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bluesky_collect import ROOT, get, queries  # noqa: E402

OUT = os.path.join(ROOT, "data", "social", "bluesky_daily")
D0, D1 = date(2026, 8, 1), date(2026, 11, 12)


def main():
    os.makedirs(OUT, exist_ok=True)
    qs = queries()
    d = D0
    while d < D1:
        fn = os.path.join(OUT, f"{d.isoformat()}.parquet")
        if os.path.exists(fn):
            d += timedelta(days=1); continue
        since, until = f"{d.isoformat()}T00:00:00Z", f"{(d + timedelta(days=1)).isoformat()}T00:00:00Z"
        rows, t0 = [], time.time()
        for q in qs:
            r = get("app.bsky.feed.searchPosts", {"q": q["q"], "since": since, "until": until, "sort": "top", "limit": 100, "lang": "en"})
            for post in (r or {}).get("posts", []):
                a, rec = post["author"], post.get("record", {})
                rows.append({"uri": post["uri"], "did": a["did"], "handle": a["handle"], "name": a.get("displayName"),
                             "created": rec.get("createdAt"), "text": rec.get("text", "")[:1000],
                             "likes": post.get("likeCount", 0), "reposts": post.get("repostCount", 0), "replies": post.get("replyCount", 0),
                             "q": q["q"], "state": q["state"], "kind": q["kind"], "event": q["event"], "candidate": q["candidate"]})
        pd.DataFrame(rows).to_parquet(fn)
        print(f"{d} posts {len(rows)} in {(time.time()-t0)/60:.1f} min", flush=True)
        d += timedelta(days=1)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
