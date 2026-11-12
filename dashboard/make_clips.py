"""Cut +/-HALF seconds around each call event from every stream on air, 240p low bitrate (for the Vercel build).

Output: <out_dir>/clips/<id>_e<k>.mp4 and <out_dir>/clips.json  {id: [{"t0":abs_utc,"t1":abs_utc,"src":"clips/.."}]}
"""
import json, os, subprocess, sys
import imageio_ffmpeg

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
from build_data import EVENTS, streams  # noqa: E402

HALF = int(os.environ.get("CLIP_HALF_S", 180))
FF = imageio_ffmpeg.get_ffmpeg_exe()


def main(out_dir):
    os.makedirs(os.path.join(out_dir, "clips"), exist_ok=True)
    res, total = {}, 0
    for s in streams():
        src = os.path.join(ROOT, "data", "window", "video", f"{s['id']}.mp4")
        if not os.path.exists(src):
            continue
        for k, e in enumerate(EVENTS):
            a, b = max(e["t"] - HALF, s["start"]), min(e["t"] + HALF, s["start"] + s["dur"])
            if b - a < 20:
                continue
            rel = f"clips/{s['id']}_e{k}.mp4"
            dst = os.path.join(out_dir, rel)
            if not os.path.exists(dst):
                cmd = [FF, "-nostdin", "-loglevel", "error", "-y", "-ss", f"{a - s['start']:.2f}", "-t", f"{b - a:.2f}", "-i", src,
                       "-vf", "scale=-2:240,fps=15", "-c:v", "libx264", "-preset", "slow", "-crf", "33",
                       "-maxrate", "95k", "-bufsize", "190k", "-c:a", "aac", "-b:a", "32k", "-ac", "1",
                       "-movflags", "+faststart", dst]
                subprocess.run(cmd, check=True)
            sz = os.path.getsize(dst); total += sz
            res.setdefault(s["id"], []).append({"t0": a, "t1": b, "src": rel})
            print(f"{s['name']:24s} e{k} {(b-a)/60:4.1f} min {sz/1e6:5.1f} MB", flush=True)
    json.dump(res, open(os.path.join(out_dir, "clips.json"), "w"))
    print(f"TOTAL {total/1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
