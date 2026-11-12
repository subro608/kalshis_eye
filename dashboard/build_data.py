"""Bundle Kalshi minute prices, stream metadata, Whisper transcripts and live-chat into dashboard/data.js.

Run:  .venv/bin/python dashboard/build_data.py
All times are UTC epoch seconds; the page renders them in US Eastern.
"""
import glob, json, os, random, re
from collections import Counter, defaultdict
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
W = os.path.join(ROOT, "data", "window")
W0 = int(pd.Timestamp("2026-11-03 16:00", tz="UTC").timestamp())   # 11:00 ET
W1 = int(pd.Timestamp("2026-11-04 20:00", tz="UTC").timestamp())   # 15:00 ET
EVENTS = [  # from Kalshi market early-close / AP-call markets
    {"t": int(pd.Timestamp("2026-11-04 04:46:52", tz="UTC").timestamp()), "label": "Senate control settles (Kalshi): D"},
    {"t": int(pd.Timestamp("2026-11-04 05:02:53", tz="UTC").timestamp()), "label": "House control settles (Kalshi): D"},
    {"t": int(pd.Timestamp("2026-11-04 07:19:29", tz="UTC").timestamp()), "label": "AP calls House"},
]
CHAT_SAMPLE_PER_MIN = 12
random.seed(0)


def streams():
    items = json.load(open(os.path.join(W, "items.json")))
    out = []
    for name, lean, plat, vid, url in items:
        mp = os.path.join(W, "meta", f"{vid}.info.json")
        if not os.path.exists(mp):
            continue
        d = json.load(open(mp))
        start = d.get("release_timestamp") or d.get("timestamp")
        vf = os.path.join(W, "video", f"{vid}.mp4")
        out.append({"id": vid, "name": name, "lean": lean, "platform": plat, "url": url,
                    "title": d.get("title"), "start": start, "dur": d.get("duration"),
                    "views": d.get("view_count"), "video": f"../data/window/video/{vid}.mp4" if os.path.exists(vf) else None})
    return out


def transcripts(ss):
    res = {}
    for s in ss:
        p = os.path.join(W, "transcripts", f"{s['id']}.json")
        if os.path.exists(p):
            segs = json.load(open(p))["segments"]
            res[s["id"]] = [[round(x["start"], 1), round(x["end"], 1), x["text"]] for x in segs if x["text"]]
    return res


def chat_messages(path):
    """yt-dlp live_chat.json: one JSON object per line (replayChatItemAction)."""
    for line in open(path, encoding="utf-8", errors="ignore"):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        a = o.get("replayChatItemAction", {})
        off = a.get("videoOffsetTimeMsec")
        for act in a.get("actions", []):
            it = act.get("addChatItemAction", {}).get("item", {})
            r = it.get("liveChatTextMessageRenderer") or it.get("liveChatPaidMessageRenderer")
            if not r or off is None:
                continue
            txt = "".join(run.get("text", "") or (run.get("emoji", {}).get("shortcuts") or [""])[0]
                          for run in r.get("message", {}).get("runs", []))
            yield int(off) / 1000.0, (r.get("authorName") or {}).get("simpleText", ""), txt


def chats(ss):
    res = {}
    for s in ss:
        p = os.path.join(W, "chat", f"{s['id']}.live_chat.json")
        if not os.path.exists(p):
            continue
        per_min, counts = defaultdict(list), Counter()
        for off, author, txt in chat_messages(p):
            m = int(off // 60)
            counts[m] += 1
            per_min[m].append([round(off, 1), author[:24], txt[:200]])
        sample = []
        for m, msgs in per_min.items():
            sample += random.sample(msgs, min(CHAT_SAMPLE_PER_MIN, len(msgs)))
        sample.sort()
        res[s["id"]] = {"per_min": sorted(counts.items()), "msgs": sample, "total": sum(counts.values())}
    return res


def race_info(series, ticker, title):
    """kind (senate/house/gov/control/apcall), state, district, party of the YES side."""
    m = re.match(r"^(SENATEPARTY-?|SENATE)([A-Z]{2})(S?)$", series)
    kind = state = dist = None
    if m: kind, state, dist = "senate", m.group(2), ("special" if m.group(3) else None)
    elif (m := re.match(r"^HOUSE([A-Z]{2})(\d+)$", series)): kind, state, dist = "house", m.group(1), int(m.group(2))
    elif (m := re.match(r"^(GOVPARTY|KXGOV)([A-Z]{2})$", series)): kind, state = "gov", m.group(2)
    elif series.startswith("CONTROL"): kind = "control"
    elif series.startswith("KXAPCALL"): kind = "apcall"
    suf = ticker.rsplit("-", 1)[-1]
    t = (title or "").lower()
    party = "D" if suf == "D" or "democrat" in t else "R" if suf == "R" or "republican" in t else "O"
    return kind, state, dist, party


def kalshi():
    mk = pd.read_parquet(os.path.join(W, "kalshi", "markets.parquet"))
    c = pd.read_parquet(os.path.join(W, "kalshi", "minute_candles.parquet"))
    grid = list(range(W0 + 60, W1 + 1, 60))
    out = []
    for _, m in mk.iterrows():
        g = c[c.ticker == m.ticker].set_index("ts").sort_index()
        px = g["close"].reindex(grid).ffill()
        if px.notna().sum() < 10:
            continue
        kind, state, dist, party = race_info(m.series_ticker, m.ticker, m.title)
        out.append({"ticker": m.ticker, "series": m.series_ticker, "event": m.event_ticker, "title": m.title,
                    "sub": m.yes_sub_title, "result": m.result, "close_time": m.close_time,
                    "volume_total": float(m.volume_fp or 0), "kind": kind, "state": state, "dist": dist, "party": party,
                    "px": [None if pd.isna(v) else round(float(v), 3) for v in px]})
    return {"t0": grid[0], "step": 60, "markets": out}


def geo():
    """US state topology (pre-projected Albers USA, 975x610) + congressional-district interior points."""
    import zipfile
    g = os.path.join(ROOT, "data", "geo")
    topo = json.load(open(os.path.join(g, "states-albers-10m.json")))
    z = zipfile.ZipFile(os.path.join(g, "cd_gaz.zip"))
    lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    hdr = lines[0].split("|"); cd = {}
    for ln in lines[1:]:
        r = dict(zip(hdr, ln.split("|")))
        if not r["GEOID"][2:].isdigit(): continue
        d = int(r["GEOID"][2:]) or 1          # at-large "00" -> 1
        cd[f"{r['USPS']}-{d}"] = [round(float(r["INTPTLAT"]), 4), round(float(r["INTPTLONG"].strip()), 4), round(float(r["ALAND_SQMI"]))]
    return {"states": topo, "cd": cd}


def main():
    ss = streams()
    clips_json = os.environ.get("CLIPS_JSON")   # deploy build: clips instead of full local video
    if clips_json:
        cl = json.load(open(clips_json))
        for x in ss:
            x["video"] = None
            x["clips"] = cl.get(x["id"], [])
    data = {"window": [W0, W1], "events": EVENTS, "streams": ss, "transcripts": transcripts(ss),
            "chat": chats(ss), "kalshi": kalshi(), "geo": geo()}
    p = os.environ.get("DATA_OUT") or os.path.join(ROOT, "dashboard", "data.js")
    with open(p, "w") as f:
        f.write("window.DATA=")
        json.dump(data, f, separators=(",", ":"))
        f.write(";")
    print("wrote", p, f"{os.path.getsize(p)/1e6:.1f} MB", "| streams", len(ss), "| transcripts", len(data["transcripts"]),
          "| chats", len(data["chat"]), "| markets", len(data["kalshi"]["markets"]))


if __name__ == "__main__":
    main()
