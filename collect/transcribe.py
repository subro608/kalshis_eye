"""Whisper large-v3-turbo transcription of downloaded election-night videos (GPU).

For each data/window/video/<id>.mp4 -> data/window/transcripts/<id>.json
  {"id":..., "segments":[{"start":s, "end":s, "text":...}, ...]}  (seconds from video start)
Audio is decoded with ffmpeg to 16 kHz mono and processed in 20-minute blocks.
"""
import glob, json, os, subprocess, sys, time
import numpy as np, torch
from transformers import pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VID = os.path.join(ROOT, "data/window/video")
OUT = os.path.join(ROOT, "data/window/transcripts")
SR, BLOCK = 16000, 20 * 60
# static ffmpeg (the container's ffmpeg breaks under --nv because of injected host GL libs)
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")


def blocks(path):
    cmd = [FFMPEG, "-nostdin", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = SR * BLOCK * 4
    i = 0
    while True:
        buf = p.stdout.read(n)
        if not buf: break
        yield i * BLOCK, np.frombuffer(buf, dtype=np.float32).copy()
        i += 1
    p.wait()


def main():
    os.makedirs(OUT, exist_ok=True)
    asr = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo",
                   torch_dtype=torch.float16, device="cuda:0")
    files = sorted(f for f in glob.glob(os.path.join(VID, "*.mp4")) if os.path.basename(f).count(".") == 1)
    print("files", len(files), flush=True)
    for f in files:
        vid = os.path.basename(f).rsplit(".", 1)[0]
        out = os.path.join(OUT, f"{vid}.json")
        if os.path.exists(out): continue
        t0, segs = time.time(), []
        for off, audio in blocks(f):
            r = asr({"raw": audio, "sampling_rate": SR}, chunk_length_s=30, batch_size=32, return_timestamps=True,
                    generate_kwargs={"language": "en", "task": "transcribe"})
            for c in r["chunks"]:
                a, b = c["timestamp"]
                if a is None: continue
                segs.append({"start": round(off + a, 2), "end": round(off + (b if b is not None else a + 5), 2),
                             "text": c["text"].strip()})
            print(f"  {vid} block@{off/3600:.2f}h segs={len(segs)}", flush=True)
        if not segs:
            raise RuntimeError(f"no transcript segments for {vid} - audio decode failed?")
        json.dump({"id": vid, "model": "openai/whisper-large-v3-turbo", "segments": segs}, open(out, "w"))
        print(f"DONE {vid} {len(segs)} segs in {(time.time()-t0)/60:.1f} min", flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
