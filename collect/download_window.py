"""Download election-night streams (360p video + metadata + live chat + auto-captions).

Window of interest: Senate call (~04:00-05:00Z Nov 4) and House call (07:19Z Nov 4) +/- 12 h.
Hard cap: stops starting new downloads once data/window exceeds CAP_GB.
Output: data/window/{meta,video,chat,captions}/ ; log of failures in logs/download_window.log
"""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
YTDLP = os.path.join(ROOT, ".venv", "bin", "yt-dlp")
OUT = os.path.join(ROOT, "data", "window")
CAP_GB = 50
sys.path.insert(0, HERE)


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


ITEMS = [  # (streamer, lean, platform, id, url)
    ("Hasan Piker", "L", "twitch", "v2918627486", "https://www.twitch.tv/videos/2918627486"),
    ("Hasan Piker", "L", "youtube", "aO61Eyw-jEs", "https://www.youtube.com/watch?v=aO61Eyw-jEs"),
    ("Brian Tyler Cohen", "L", "youtube", "SEqjgdf0EMc", "https://www.youtube.com/watch?v=SEqjgdf0EMc"),
    ("The Young Turks", "L", "youtube", "yve_Ai2MHGc", "https://www.youtube.com/watch?v=yve_Ai2MHGc"),
    ("Steven Crowder", "R", "youtube", "EHu5nlFzPLM", "https://www.youtube.com/watch?v=EHu5nlFzPLM"),
    ("Tim Pool", "R", "youtube", "bG0c5Xzj-70", "https://www.youtube.com/watch?v=bG0c5Xzj-70"),
    ("Ben Shapiro / Daily Wire", "R", "youtube", "73cHh3h_NJ8", "https://www.youtube.com/watch?v=73cHh3h_NJ8"),
    ("Charlie Kirk Show", "R", "youtube", "8vy9x-YcOjs", "https://www.youtube.com/watch?v=8vy9x-YcOjs"),
]


def used_gb():
    tot = 0
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            try: tot += os.path.getsize(os.path.join(dp, f))
            except OSError: pass
    return tot / 1e9


def run(cmd, label):
    print(">>", label, flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    tail = (r.stderr or "").strip().splitlines()[-2:]
    print(f"   rc={r.returncode} {' | '.join(tail)[:300]}", flush=True)
    return r.returncode == 0


def main():
    ff = ffmpeg()
    for d in ["meta", "video", "chat", "captions"]:
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    json.dump(ITEMS, open(os.path.join(OUT, "items.json"), "w"), indent=1)
    common = [YTDLP, "--ffmpeg-location", ff, "--sleep-requests", "1", "--retries", "10",
              "--fragment-retries", "20", "--no-progress", "--no-overwrites", "--continue"]
    # pass 1: metadata (cheap)
    for name, lean, plat, vid, url in ITEMS:
        if not os.path.exists(os.path.join(OUT, "meta", f"{vid}.info.json")):
            run(common + ["--skip-download", "--write-info-json", "-o", os.path.join(OUT, "meta", "%(id)s.%(ext)s"), url],
                f"meta {name} {vid}")
    # pass 2: 360p video
    for name, lean, plat, vid, url in ITEMS:
        gb = used_gb()
        if gb > CAP_GB:
            print(f"CAP REACHED ({gb:.1f} GB) - skipping remaining video", flush=True); break
        fmt = "360p/360p30/b[height<=360]" if plat == "twitch" else "18/bv*[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360]"
        ok = run(common + ["-f", fmt, "--merge-output-format", "mp4", "-N", "4",
                           "-o", os.path.join(OUT, "video", f"{vid}.%(ext)s"), url], f"video {name} {vid} (used {gb:.1f} GB)")
        if not ok: print("FAILED video", vid, flush=True)
    # pass 3: YouTube live-chat replay + English auto-captions (text only)
    for name, lean, plat, vid, url in ITEMS:
        if plat != "youtube":
            continue
        run(common + ["--skip-download", "--write-subs", "--sub-langs", "live_chat",
                      "-o", os.path.join(OUT, "chat", "%(id)s.%(ext)s"), url], f"chat {name} {vid}")
        run(common + ["--skip-download", "--write-auto-subs", "--sub-langs", "en", "--sub-format", "json3",
                      "-o", os.path.join(OUT, "captions", "%(id)s.%(ext)s"), url], f"captions {name} {vid}")
    print(f"DONE total {used_gb():.2f} GB", flush=True)


if __name__ == "__main__":
    main()
