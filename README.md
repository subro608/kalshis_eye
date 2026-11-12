# kalshis_eye

A Palantir-style "night ops" dashboard that lines up **Kalshi prediction-market prices** with what
**political streamers on the left and right** were saying, and how their chat reacted, around the
calls in the **2026 US midterms**.

Research question: do partisan streamers, their audiences and social media lead, lag or distort
Kalshi prices, and does that differ between left and right, or matter more in thinly polled races?

## What it shows
- **Timeline:** Kalshi Senate and House control probability (minute data), the call moments
  (Senate control settled 11:46 PM ET, House 12:02 AM ET, AP House call 2:19 AM ET), and one lane per
  stream with chat or transcript activity and search hits.
- **Synced players:** every stream jumps to the same wall-clock moment.
- **Transcripts / chat / search:** Whisper transcripts and YouTube live-chat replay at the cursor;
  keyword search split by left and right.
- **Races:** every Senate, House-district and governor market Kalshi listed, shown on a state tile map
  plus a sortable board (60-minute move, closest race, volume) with winners.

Window: Nov 3 11:00 ET to Nov 4 15:00 ET (about ±12 h around the calls).

## Pipeline
| Step | Script | Output |
|---|---|---|
| Kalshi midterm markets + hourly candles (public API, no auth) | `collect/kalshi_collect.py` | `data/kalshi/` |
| Minute candles in the window: control, AP-call markets, all races | `collect/kalshi_window_minute.py` | `data/window/kalshi/` |
| Streamer video listings since Aug 1 (metadata only) | `collect/streamer_metadata.py` | `data/streamers/` |
| Election-night streams: 360p video, info, live chat, captions (50 GB cap) | `collect/download_window.py` | `data/window/` |
| Whisper large-v3-turbo transcripts (GPU, SLURM) | `collect/transcribe.py`, `collect/transcribe.sbatch` | `data/window/transcripts/` |
| Bundle for the page | `dashboard/build_data.py` | `dashboard/data.js` |
| Local viewer with HTTP Range (video seeking) | `dashboard/serve.py` | http://localhost:8817/dashboard/index.html |
| Hosted build: ±3 min 240p clips around each call + basic-auth middleware | `dashboard/make_clips.py`, `dashboard/build_site.sh` | static site for Vercel |

Streams (default list, editable in `collect/`): Hasan Piker (Twitch + YouTube), Brian Tyler Cohen,
The Young Turks (left); Steven Crowder, Tim Pool, Daily Wire / Ben Shapiro, Charlie Kirk Show (right).

## Quick start
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python collect/kalshi_collect.py
.venv/bin/python collect/kalshi_window_minute.py
.venv/bin/python collect/streamer_metadata.py
.venv/bin/python collect/download_window.py
sbatch collect/transcribe.sbatch            # or run collect/transcribe.py on any CUDA machine
.venv/bin/python dashboard/build_data.py
.venv/bin/python dashboard/serve.py 8817
```

## Data policy
This repo holds **code only**. Downloaded streams, chat logs, transcripts and the bundled `data.js`
are third-party content collected for private research and are git-ignored. Kalshi data comes from
Kalshi's public market-data API.

## Not yet included
X/Twitter (needs a paid API key) and Twitch chat replay.
