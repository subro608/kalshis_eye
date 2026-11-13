"""VoteHub polls (CC BY 4.0, https://api.votehub.com/polls) for Kalshi races since Aug 1, merged with Wikipedia polls.

Writes data/polls/polls_votehub.parquet and the merged data/polls/polls.parquet (source column: wikipedia / votehub).
Duplicates (same race, same pollster, end dates within 2 days, D within 1 pt) keep the Wikipedia row.
"""
import json, os, re, sys
import pandas as pd, requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from polls_wikipedia import ROOT, OUT, STATES, races  # noqa: E402

NAME2AB = {v: k for k, v in STATES.items()}


def main():
    raw = os.path.join(OUT, "raw", "votehub_polls.json")
    os.makedirs(os.path.dirname(raw), exist_ok=True)
    r = requests.get("https://api.votehub.com/polls", headers={"User-Agent": "kalshis-eye-research/0.1"}, timeout=120)
    r.raise_for_status(); open(raw, "w").write(r.text)
    polls = r.json()
    rc = races()
    rows = []
    for p in polls:
        if (p.get("end_date") or "") < "2026-08-01": continue
        t, subj = p.get("poll_type"), p.get("subject") or ""
        key = None
        if t == "us-representative":
            m = re.search(r"([A-Z]{2})-(\d{2})", p.get("seat_name") or subj)
            if m: key = ("house", m.group(1), int(m.group(2)) or 1)
        elif t in ("us-senator", "governor"):
            st = next((ab for nm, ab in NAME2AB.items() if nm in subj), None)
            if st:
                special = "special" in subj.lower()
                key = ("senate", st, "special" if special else None) if t == "us-senator" else ("gov", st, None)
        if not key or key not in rc: continue
        race = rc[key]
        if not (race["D"] and race["R"]): continue
        dl, rl = race["D"].split()[-1].lower(), race["R"].split()[-1].lower()
        ans = {a["choice"].lower(): a["pct"] for a in p.get("answers", [])}
        dv = next((v for c, v in ans.items() if dl in c), None); rv = next((v for c, v in ans.items() if rl in c), None)
        if dv is None or rv is None: continue
        rows.append({"kind": key[0], "state": key[1], "dist": None if key[2] is None else str(key[2]), "events": "|".join(sorted(race["events"])),
                     "page": p.get("url") or "", "pollster": (p.get("pollster") or "")[:80], "end": p["end_date"],
                     "sample": f"{p.get('sample_size') or ''} {p.get('population') or ''}".strip(), "moe": "",
                     "D_name": race["D"], "R_name": race["R"], "D": float(dv), "R": float(rv),
                     "section": f"votehub {t}{' · partisan ' + p['partisan'] if p.get('partisan') else ''}{' · internal' if p.get('internal') else ''}",
                     "source": "votehub"})
    vh = pd.DataFrame(rows)
    vh.to_parquet(os.path.join(OUT, "polls_votehub.parquet"))
    wk = pd.read_parquet(os.path.join(OUT, "polls_wikipedia.parquet")).assign(source="wikipedia")
    wk["dist"] = wk["dist"].where(wk["dist"].notna() & (wk["dist"] != "None"), None)
    norm = lambda s: re.sub(r"[^a-z]", "", str(s).lower())[:8]
    keep = []
    for _, v in vh.iterrows():
        same = wk[(wk.kind == v.kind) & (wk.state == v.state) & (wk.dist.fillna("") == (v.dist or ""))]
        dup = same[(same.pollster.map(norm) == norm(v.pollster)) &
                   ((pd.to_datetime(same.end) - pd.to_datetime(v.end)).abs().dt.days <= 2) & ((same.D - v.D).abs() <= 1)]
        keep.append(dup.empty)
    vh_new = vh[keep] if len(vh) else vh
    allp = pd.concat([wk, vh_new], ignore_index=True)
    allp["dist"] = allp["dist"].astype("string")
    allp.to_parquet(os.path.join(OUT, "polls.parquet")); allp.to_csv(os.path.join(OUT, "polls.csv"), index=False)
    s = allp.assign(k=allp.state + "-" + allp.dist.fillna("x")).groupby("kind").agg(polls=("k", "size"), races=("k", "nunique"))
    print(f"votehub matched {len(vh)} (new after dedupe {len(vh_new)}); merged {len(allp)} polls"); print(s.to_string())


if __name__ == "__main__":
    main()
