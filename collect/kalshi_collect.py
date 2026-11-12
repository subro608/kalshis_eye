"""Collect Kalshi 2026 US-midterm market metadata + hourly candlesticks (public API, no auth).

Output: data/kalshi/{series.json, markets.parquet, candles/<series>.parquet, log}
Window: candles from START to END (UTC), hourly.
"""
import json, os, re, sys, time
from datetime import datetime, timezone
import requests
import pandas as pd

B = "https://api.elections.kalshi.com/trade-api/v2"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "kalshi")
START = int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 11, 12, tzinfo=timezone.utc).timestamp())
# markets settling around election night / counting
CLOSE_MIN = int(datetime(2026, 11, 3, tzinfo=timezone.utc).timestamp())
CLOSE_MAX = int(datetime(2027, 1, 31, tzinfo=timezone.utc).timestamp())
# US midterm general-election series patterns (ticker prefixes)
US_PAT = re.compile(r"^(SENATE|HOUSE|GOVPARTY|KXGOV|KXSENATE|KXHOUSE|KXCONTROL|KXDHOUSE|KXRGOV|"
                    r"KXDEMTRIFECTA|KXLTGOV|KXAPCALL|KXEXITPOLL|KXTRUMPEXIT|KXCLOSEST|KXMESEN|KXTXSEN|"
                    r"KXNESEN|KXIASEN|KXMSSEN|KXHOUSEPOP|KXBALANCE|KXSWEEP|KXMIDTERM)")
s = requests.Session()
s.headers["User-Agent"] = "research-data-collector/0.1"


def get(path, params=None, tries=6):
    for i in range(tries):
        try:
            r = s.get(B + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 ** i); continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            time.sleep(0.12)
            return r.json()
        except requests.RequestException as e:
            print("retry", path, e, flush=True); time.sleep(2 ** i)
    raise RuntimeError(path)


def main():
    os.makedirs(os.path.join(OUT, "candles"), exist_ok=True)
    series = []
    for cat in ["Elections", "Politics"]:
        series += get("/series", {"category": cat})["series"]
    series = {x["ticker"]: x for x in series}
    json.dump(series, open(os.path.join(OUT, "series_elections_politics.json"), "w"))
    us = sorted(t for t in series if US_PAT.match(t))
    print("candidate US series:", len(us), flush=True)

    rows = []
    for i, st in enumerate(us):
        cur = None
        while True:
            p = {"series_ticker": st, "limit": 1000, "min_close_ts": CLOSE_MIN, "max_close_ts": CLOSE_MAX}
            if cur: p["cursor"] = cur
            d = get("/markets", p)
            if not d: break
            for m in d.get("markets", []):
                m["series_ticker"] = st
                m["series_title"] = series[st].get("title")
                m["category"] = series[st].get("category")
                rows.append(m)
            cur = d.get("cursor")
            if not cur: break
        if i % 50 == 0:
            print(f"series {i}/{len(us)} markets so far {len(rows)}", flush=True)
    mk = pd.DataFrame(rows)
    for c in mk.columns:
        if mk[c].map(lambda v: isinstance(v, (list, dict))).any():
            mk[c] = mk[c].map(json.dumps)
    mk.to_parquet(os.path.join(OUT, "markets.parquet"))
    print("markets:", len(mk), "series with markets:", mk.series_ticker.nunique(), flush=True)

    for j, (st, g) in enumerate(mk.groupby("series_ticker")):
        fn = os.path.join(OUT, "candles", f"{st}.parquet")
        if os.path.exists(fn):
            continue
        out = []
        for t in g.ticker:
            d = get(f"/series/{st}/markets/{t}/candlesticks",
                    {"start_ts": START, "end_ts": END, "period_interval": 60})
            for c in (d or {}).get("candlesticks", []):
                out.append({"ticker": t, "ts": c["end_period_ts"],
                            "close": c["price"].get("close_dollars"), "mean": c["price"].get("mean_dollars"),
                            "bid_close": c["yes_bid"].get("close_dollars"), "ask_close": c["yes_ask"].get("close_dollars"),
                            "volume": c.get("volume_fp"), "open_interest": c.get("open_interest_fp")})
        df = pd.DataFrame(out)
        if len(df):
            for c in ["close", "mean", "bid_close", "ask_close", "volume", "open_interest"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["time"] = pd.to_datetime(df.ts, unit="s", utc=True)
        df.to_parquet(fn)
        if j % 25 == 0:
            print(f"candles series {j}/{mk.series_ticker.nunique()} ({st}: {len(df)} rows)", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
