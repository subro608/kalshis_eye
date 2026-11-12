"""Minute candles in the election-night window for control markets, AP-call markets and top races."""
import os, time
from datetime import datetime, timezone
import pandas as pd, requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = "https://api.elections.kalshi.com/trade-api/v2"
W0 = int(datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc).timestamp())
W1 = int(datetime(2026, 11, 4, 20, 0, tzinfo=timezone.utc).timestamp())
s = requests.Session()


def get(path, params=None):
    for i in range(6):
        r = s.get(B + path, params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** i); continue
        if r.status_code == 404: return None
        r.raise_for_status(); time.sleep(0.15); return r.json()


def market(t):
    return (get(f"/markets/{t}") or {}).get("market")


def main():
    mk = pd.read_parquet(os.path.join(ROOT, "data/kalshi/markets.parquet"))
    mk["vol"] = pd.to_numeric(mk.volume_fp, errors="coerce")
    # every Senate / House-district / Governor race market Kalshi listed (Kalshi only lists competitive districts)
    races = mk[mk.series_ticker.str.match(r"^(SENATE|SENATEPARTY|HOUSE[A-Z]{2}\d|GOVPARTY|KXGOV[A-Z]{2}$)")]
    top = races.sort_values("vol", ascending=False)
    tickers = ["CONTROLH-2026-D", "CONTROLH-2026-R", "CONTROLS-2026-D", "CONTROLS-2026-R"]
    tickers += [t for t in mk.ticker if t.startswith(("KXAPCALLHOUSE", "KXAPCALLSENATE"))]
    tickers += list(top.ticker)
    # also scan every race series directly for its 2026 markets (catches still-open ones, e.g. Alaska RCV)
    import json as _j, re as _re
    ser = _j.load(open(os.path.join(ROOT, "data/kalshi/series_elections_politics.json")))
    pat = _re.compile(r"^(SENATE[A-Z]{2}S?|SENATEPARTY-?[A-Z]{2}|HOUSE[A-Z]{2}\d+|GOVPARTY[A-Z]{2}|KXGOV[A-Z]{2})$")
    for st in sorted(t for t in ser if pat.match(t)):
        d = get("/markets", {"series_ticker": st, "limit": 200}) or {}
        tickers += [m["ticker"] for m in d.get("markets", []) if "-26" in m["ticker"]]
    meta, rows = [], []
    for t in dict.fromkeys(tickers):
        m = market(t)
        if not m: continue
        st = t.split("-")[0]
        meta.append({k: m.get(k) for k in ["ticker", "event_ticker", "title", "yes_sub_title", "result", "close_time",
                                            "volume_fp", "status"]} | {"series_ticker": st})
        d = get(f"/series/{st}/markets/{t}/candlesticks", {"start_ts": W0, "end_ts": W1, "period_interval": 1})
        for c in (d or {}).get("candlesticks", []):
            rows.append({"ticker": t, "ts": c["end_period_ts"], "close": c["price"].get("close_dollars"),
                         "mean": c["price"].get("mean_dollars"), "bid": c["yes_bid"].get("close_dollars"),
                         "ask": c["yes_ask"].get("close_dollars"), "volume": c.get("volume_fp")})
        print(t, len(rows), flush=True)
    os.makedirs(os.path.join(ROOT, "data/window/kalshi"), exist_ok=True)
    pd.DataFrame(meta).to_parquet(os.path.join(ROOT, "data/window/kalshi/markets.parquet"))
    df = pd.DataFrame(rows)
    for c in ["close", "mean", "bid", "ask", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.to_parquet(os.path.join(ROOT, "data/window/kalshi/minute_candles.parquet"))
    print("DONE", len(meta), "markets", len(df), "rows", flush=True)


if __name__ == "__main__":
    main()
