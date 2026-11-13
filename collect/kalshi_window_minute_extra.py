"""Add the House races Kalshi lists under KXHOUSERACE (one series, ~340 districts) and KXHOUSE<ST><N> series to the
election-night minute data. Appends to data/window/kalshi/{markets,minute_candles}.parquet (skips tickers already there).
A `race_series` column normalises every race to SENATE<ST>[S] / HOUSE<ST><N> / GOVPARTY<ST> naming."""
import os, re
import pandas as pd
from kalshi_window_minute import ROOT, W0, W1, get, market

WK = os.path.join(ROOT, "data/window/kalshi")


def race_series(series, ticker):
    m = re.match(r"^KXHOUSERACE-([A-Z]{2})(\d+)-", ticker) or re.match(r"^KXHOUSE([A-Z]{2})(\d+)$", series)
    return f"HOUSE{m.group(1)}{int(m.group(2))}" if m else series


def main():
    mk = pd.read_parquet(os.path.join(ROOT, "data/kalshi/markets.parquet"))
    want = mk[mk.series_ticker.str.match(r"^(KXHOUSERACE|KXHOUSE[A-Z]{2}\d+)$") & mk.ticker.str.contains("-26")]
    wm = pd.read_parquet(os.path.join(WK, "markets.parquet")); wc = pd.read_parquet(os.path.join(WK, "minute_candles.parquet"))
    have = set(wm.ticker); meta, rows = [], []
    for st, t in zip(want.series_ticker, want.ticker):
        if t in have: continue
        m = market(t)
        if not m: continue
        meta.append({k: m.get(k) for k in ["ticker", "event_ticker", "title", "yes_sub_title", "result", "close_time",
                                            "volume_fp", "status"]} | {"series_ticker": st})
        d = get(f"/series/{st}/markets/{t}/candlesticks", {"start_ts": W0, "end_ts": W1, "period_interval": 1})
        for c in (d or {}).get("candlesticks", []):
            rows.append({"ticker": t, "ts": c["end_period_ts"], "close": c["price"].get("close_dollars"),
                         "mean": c["price"].get("mean_dollars"), "bid": c["yes_bid"].get("close_dollars"),
                         "ask": c["yes_ask"].get("close_dollars"), "volume": c.get("volume_fp")})
        print(t, len(rows), flush=True)
    wm = pd.concat([wm, pd.DataFrame(meta)], ignore_index=True)
    wm["race_series"] = [race_series(s, t) for s, t in zip(wm.series_ticker, wm.ticker)]
    df = pd.DataFrame(rows)
    for c in ["close", "mean", "bid", "ask", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    wc = pd.concat([wc, df], ignore_index=True)
    wm.to_parquet(os.path.join(WK, "markets.parquet")); wc.to_parquet(os.path.join(WK, "minute_candles.parquet"))
    print("DONE added", len(meta), "markets", len(df), "rows; total", len(wm), "markets", flush=True)


if __name__ == "__main__":
    main()
