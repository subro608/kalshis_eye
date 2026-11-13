"""General-election polls since Aug 1 2026 for every Kalshi race, from Wikipedia race pages (CC BY-SA).

Pages: "2026 United States Senate election in <State>" (+ special), "2026 <State> gubernatorial election",
       "2026 United States House of Representatives elections in <State>" (per-district sections).
Keeps only tables under a General-election > Polling heading whose candidate columns match the Kalshi D and R
nominees (drops hypothetical match-ups). Output: data/polls/polls.parquet (one row per poll).
"""
import io, os, re, time
from datetime import datetime
import pandas as pd, requests
from bs4 import BeautifulSoup

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "polls")
API = "https://en.wikipedia.org/w/api.php"
SINCE = datetime(2026, 8, 1)
s = requests.Session()
s.headers["User-Agent"] = "kalshis-eye-research/0.1 (academic research script)"
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
          "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
          "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
          "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
          "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
          "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def page_html(title):
    for i in range(7):
        r = s.get(API, params={"action": "parse", "page": title, "prop": "text", "format": "json", "redirects": 1}, timeout=40)
        if r.status_code == 429: time.sleep(2 ** i); continue
        time.sleep(0.6)
        try: d = r.json()
        except ValueError: time.sleep(2 ** i); continue
        if "error" in d:
            if d["error"].get("code") == "missingtitle": return None
            time.sleep(2 ** i); continue
        return d["parse"]["text"]["*"]
    print("  fetch failed:", title, flush=True)
    return None


def end_date(txt):
    t = re.sub(r"\[.*?\]", "", str(txt)).replace("–", "-").replace("—", "-")
    yrs = re.findall(r"(20\d\d)", t); yr = int(yrs[-1]) if yrs else 2026
    md = re.findall(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})", t)
    if not md: return None
    mon = MONTHS.get(md[-1][0][:3].lower()); day = int(md[-1][1])
    tail = re.search(r"-\s*(\d{1,2})\s*,?\s*(20\d\d)?\s*$", t)          # "Oct 20-23, 2026"
    if tail and not re.search(r"-\s*[A-Za-z]", t): day = int(tail.group(1))
    try: return datetime(yr, mon, day)
    except (TypeError, ValueError): return None


def pct(v):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(v))
    return float(m.group(1)) if m else None


def flat(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [next((str(x) for x in reversed(c) if x and not str(x).startswith("Unnamed")), str(c[0])) for c in df.columns]
    df.columns = [re.sub(r"\[.*?\]|\s+", " ", str(c)).strip() for c in df.columns]
    return df


def poll_tables(html, district=None):
    """yield (heading path, table) for wikitables under General election > Polling (optionally within District N)."""
    soup = BeautifulSoup(html, "lxml")
    h = {2: "", 3: "", 4: "", 5: ""}
    for el in soup.find_all(["h2", "h3", "h4", "h5", "table"]):
        if el.name != "table":
            lv = int(el.name[1]); h[lv] = el.get_text(" ", strip=True)
            for k in range(lv + 1, 6): h[k] = ""
            continue
        if "wikitable" not in (el.get("class") or []): continue
        path = " > ".join(x for x in h.values() if x)
        if "poll" not in path.lower() or "general" not in path.lower(): continue
        if any(w in path.lower() for w in ["primary", "runoff", "hypothetical"]) and "general" not in h[2].lower() and "general" not in h[3].lower():
            continue
        if "hypothetical" in path.lower(): continue
        if district is not None:
            m = re.search(r"District\s+(\d+)|(\d+)(?:st|nd|rd|th)\s+district|at-large", path, re.I)
            dn = 1 if m and "at-large" in m.group(0).lower() else (int(m.group(1) or m.group(2)) if m else None)
            if dn != district: continue
        yield path, el


def races():
    mk = pd.read_parquet(os.path.join(ROOT, "data/window/kalshi/markets.parquet"))
    out = {}
    for _, m in mk.iterrows():
        mm = re.match(r"^(?:SENATEPARTY-?|SENATE)([A-Z]{2})(S?)$|^HOUSE([A-Z]{2})(\d+)$|^(?:GOVPARTY|KXGOV)([A-Z]{2})$", m.series_ticker)
        if not mm: continue
        if mm.group(1): key = ("senate", mm.group(1), "special" if mm.group(2) else None)
        elif mm.group(3): key = ("house", mm.group(3), int(mm.group(4)))
        else: key = ("gov", mm.group(5), None)
        party = "D" if m.ticker.endswith("-D") else "R" if m.ticker.endswith("-R") else "O"
        r = out.setdefault(key, {"events": set(), "D": None, "R": None})
        r["events"].add(m.event_ticker)
        if party in "DR" and m.yes_sub_title and not re.search(r"party", m.yes_sub_title, re.I): r[party] = m.yes_sub_title
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    cache, rows = {}, []
    for (kind, st, extra), r in sorted(races().items(), key=lambda x: str(x[0])):
        nm = STATES[st]
        title = {"senate": f"2026 United States Senate {'special ' if extra == 'special' else ''}election in {nm}",
                 "gov": f"2026 {nm} gubernatorial election",
                 "house": f"2026 United States House of Representatives elections in {nm}"}[kind]
        if title not in cache:
            cache[title] = page_html(title)
            # big states (e.g. California) split districts onto sub-pages linked from hatnotes: append them
            if kind == "house" and cache[title]:
                from urllib.parse import unquote
                subs = re.findall(r'href="/wiki/(2026_United_States_House_of_Representatives_elections_in_[^"#]*?_\(districts[^"#]*?\))"', cache[title])
                for sub in dict.fromkeys(subs):
                    h2 = page_html(unquote(sub).replace("_", " "))
                    if h2: cache[title] += h2
        html = cache[title]
        if not html or not (r["D"] and r["R"]): print("skip", kind, st, extra, "(no page)" if not html else "(no D/R names)", flush=True); continue
        dl, rl = r["D"].split()[-1].lower(), r["R"].split()[-1].lower()
        n0 = len(rows)
        for path, tb in poll_tables(html, extra if kind == "house" else None):
            try: df = flat(pd.read_html(io.StringIO(str(tb)))[0])
            except ValueError: continue
            cols = list(df.columns)
            src = next((c for c in cols if "poll source" in c.lower() or c.lower() == "pollster"), None)
            dcol = next((c for c in cols if "date" in c.lower()), None)
            cd = next((c for c in cols if dl in c.lower()), None); cr = next((c for c in cols if rl in c.lower()), None)
            if not (src and dcol and cd and cr): continue
            ncol = next((c for c in cols if "sample" in c.lower()), None); ecol = next((c for c in cols if "margin" in c.lower()), None)
            for _, p in df.iterrows():
                e = end_date(p[dcol]); dv, rv = pct(p[cd]), pct(p[cr])
                if not e or e < SINCE or dv is None or rv is None: continue
                rows.append({"kind": kind, "state": st, "dist": extra, "events": "|".join(sorted(r["events"])), "page": title,
                             "pollster": re.sub(r"\[.*?\]", "", str(p[src])).strip()[:80], "end": e.date().isoformat(),
                             "sample": re.sub(r"\[.*?\]", "", str(p[ncol])).strip()[:20] if ncol else "",
                             "moe": re.sub(r"\[.*?\]", "", str(p[ecol])).strip()[:12] if ecol else "",
                             "D_name": r["D"], "R_name": r["R"], "D": dv, "R": rv, "section": path[:160]})
        print(f"{kind:6s} {st}{'' if extra is None else '-' + str(extra):9s} polls since Aug 1: {len(rows) - n0}", flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["kind", "state", "dist", "pollster", "end", "D", "R"]) if rows else pd.DataFrame()
    if len(df): df["dist"] = df["dist"].astype(str)
    df.to_parquet(os.path.join(OUT, "polls_wikipedia.parquet")); df.to_csv(os.path.join(OUT, "polls_wikipedia.csv"), index=False)
    print("DONE", len(df), "polls,", df.groupby(["kind", "state", "dist"], dropna=False).ngroups if len(df) else 0, "races with polls", flush=True)


if __name__ == "__main__":
    main()
