"""List videos/streams (title, approx date, duration, views) for political streamers.

Metadata only, from public channel pages via yt-dlp flat listing (no transcripts, no media).
Output: data/streamers/{channels.json, videos.parquet}
"""
import json, os, subprocess, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
YTDLP = os.path.join(HERE, "..", ".venv", "bin", "yt-dlp")
OUT = os.path.join(HERE, "..", "data", "streamers")

# lean: L = left, R = right. Editable default list.
CHANNELS = [
    ("Hasan Piker", "L", "youtube", "https://www.youtube.com/@hasanabi"),
    ("Hasan Piker", "L", "twitch", "https://www.twitch.tv/hasanabi/videos?filter=archives&sort=time"),
    ("Destiny", "L", "youtube", "https://www.youtube.com/@destiny"),
    ("Vaush", "L", "youtube", "https://www.youtube.com/@Vaush"),
    ("Kyle Kulinski", "L", "youtube", "https://www.youtube.com/@SecularTalk"),
    ("Brian Tyler Cohen", "L", "youtube", "https://www.youtube.com/@BrianTylerCohen"),
    ("The Young Turks", "L", "youtube", "https://www.youtube.com/@TheYoungTurks"),
    ("Steven Crowder", "R", "youtube", "https://www.youtube.com/@StevenCrowder"),
    ("Tim Pool", "R", "youtube", "https://www.youtube.com/@TimcastIRL"),
    ("Ben Shapiro", "R", "youtube", "https://www.youtube.com/@BenShapiro"),
    ("Charlie Kirk Show", "R", "youtube", "https://www.youtube.com/@RealCharlieKirk"),
]
SINCE = "20260801"
N_MAX = 800


def listing(url):
    cmd = [YTDLP, "--flat-playlist", "--playlist-end", str(N_MAX), "--sleep-requests", "1",
           "--extractor-args", "youtubetab:approximate_date", "-J", url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print("FAIL", url, r.stderr[-300:], flush=True)
        return []
    d = json.loads(r.stdout)
    return d.get("entries") or []


def main():
    os.makedirs(OUT, exist_ok=True)
    json.dump(CHANNELS, open(os.path.join(OUT, "channels.json"), "w"), indent=1)
    rows = []
    for name, lean, plat, base in CHANNELS:
        tabs = [base + "/videos", base + "/streams"] if plat == "youtube" else [base]
        for url in tabs:
            ents = listing(url)
            kept = 0
            for e in ents:
                ud = e.get("upload_date")
                if ud is None and e.get("timestamp"):
                    ud = pd.to_datetime(e["timestamp"], unit="s").strftime("%Y%m%d")
                if ud and ud < SINCE:
                    continue
                kept += 1
                rows.append({"streamer": name, "lean": lean, "platform": plat,
                             "tab": url.rsplit("/", 1)[-1].split("?")[0], "id": e.get("id"),
                             "title": e.get("title"), "upload_date": ud, "timestamp": e.get("timestamp"),
                             "duration_s": e.get("duration"), "view_count": e.get("view_count"),
                             "url": e.get("url")})
            print(f"{name:20s} {plat:7s} {url.rsplit('/',1)[-1][:20]:20s} listed {len(ents):4d} kept(since {SINCE}) {kept}", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(OUT, "videos.parquet"))
    df.to_csv(os.path.join(OUT, "videos.csv"), index=False)
    print("TOTAL", len(df), flush=True)


if __name__ == "__main__":
    main()
