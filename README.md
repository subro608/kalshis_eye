# kalshis_eye

A God's-Eye-View / Palantir-style "night ops" dashboard that lines up **Kalshi prediction-market prices** with what
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
- **Map:** a real US map (Albers USA) in Senate / Governor / House modes. States are coloured by D win
  probability at the cursor, and House districts show as glowing markers at Census interior points, sized
  by volume. Callouts with leader lines mark the biggest 60-minute movers, rings pulse as races settle,
  and target brackets mark the selection.
- **Race card:** Kalshi-style price chart for the selected race (1H / 6H / 12H / night / since Aug 1).
  The since-Aug view adds poll results as circles and daily Bluesky mention counts as bars.
- **Social:** Bluesky posts per state (all, or only authors whose profile says they live there), around
  the cursor, across the night, or since Aug 1.
- **HUD:** glass panels (layers, CCTV-style feed wall, target card, contacts roster), a timeline dock
  and NVG / FLIR / CRT visual presets.

Window: Nov 3 11:00 ET to Nov 4 15:00 ET (about ±12 h around the calls).

## Pipeline
| Step | Script | Output |
|---|---|---|
| Kalshi midterm markets + hourly candles (public API, no auth) | `collect/kalshi_collect.py` | `data/kalshi/` |
| US state topology + congressional-district gazetteer | `collect/fetch_geo.sh` | `data/geo/` |
| Minute candles in the window: control, AP-call markets, all races | `collect/kalshi_window_minute.py` | `data/window/kalshi/` |
| Streamer video listings since Aug 1 (metadata only) | `collect/streamer_metadata.py` | `data/streamers/` |
| Election-night streams: 360p video, info, live chat, captions (50 GB cap) | `collect/download_window.py` | `data/window/` |
| Whisper large-v3-turbo transcripts (GPU, SLURM) | `collect/transcribe.py`, `collect/transcribe.sbatch` | `data/window/transcripts/` |
| Bluesky posts on election night + author profiles (self-reported home state) | `collect/bluesky_collect.py` | `data/social/` |
| Bluesky day-by-day backfill since Aug 1 | `collect/bluesky_backfill.py` | `data/social/bluesky_daily/` |
| General-election polls since Aug 1: Wikipedia (CC BY-SA) | `collect/polls_wikipedia.py` | `data/polls/polls_wikipedia.parquet` |
| VoteHub polls (CC BY 4.0), merged and deduped with Wikipedia | `collect/polls_votehub.py` | `data/polls/polls.parquet` |
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
bash collect/fetch_geo.sh
.venv/bin/python collect/streamer_metadata.py
.venv/bin/python collect/bluesky_collect.py; .venv/bin/python collect/bluesky_backfill.py
.venv/bin/python collect/polls_wikipedia.py; .venv/bin/python collect/polls_votehub.py
.venv/bin/python collect/download_window.py
sbatch collect/transcribe.sbatch            # or run collect/transcribe.py on any CUDA machine
.venv/bin/python dashboard/build_data.py
.venv/bin/python dashboard/serve.py 8817
```

## Data policy
This repo holds **code only**. Downloaded streams, chat logs, transcripts, Bluesky posts and the bundled
`data.js` are third-party content collected for private research and are git-ignored. Kalshi data comes
from Kalshi's public market-data API. See [AGENTS.md](AGENTS.md) for the full data inventory, sources,
licences and handling rules.

## Not yet included
- **X/Twitter:** the API's recent search covers only 7 days, and the full archive costs ~$42k/month.
  Bluesky is used instead.
- **Twitch chat replay**, and live chat for streams that have no replay (Crowder, Daily Wire, Hasan's
  YouTube stream).
- **Reddit:** needs OAuth credentials.
- **House polling is sparse:** 29 of 64 Kalshi House districts had no public general-election poll since
  Aug 1. This is a property of the data, not a gap in collection.
