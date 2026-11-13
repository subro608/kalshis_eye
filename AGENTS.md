# AGENTS.md — kalshis_eye

Guide for coding agents (and people) working in this repo: what the website is, what data it uses,
where every dataset was pulled from, and the rules for handling it.

## 1. What this project is
Research for the **Kalshi Research grant** (2-page proposal, due 2026-11-18). Question: do partisan
political streamers, their chat audiences and social media **lead, lag or distort Kalshi prices**,
and is that different for left vs right, or in thinly polled races?

Case study: the **2026 US midterm election night**. Democrats won both chambers.

| Moment (from Kalshi market close / settle times) | UTC | ET |
|---|---|---|
| Analysis window start | 2026-11-03 16:00 | Nov 3 11:00 AM |
| Senate control settled (`CONTROLS-2026`) | 2026-11-04 04:46:52 | 11:46 PM |
| House control settled (`CONTROLH-2026`) | 2026-11-04 05:02:53 | 12:02 AM |
| AP House call market (`KXAPCALLHOUSE`) | 2026-11-04 07:19:29 | 2:19 AM |
| Analysis window end | 2026-11-04 20:00 | Nov 4 3:00 PM |

Long-range context series run from **2026-08-01** to 2026-11-12.

## 2. The website ("Kalshi's Eye" / Midterm Night Ops)
A single static page, `dashboard/index.html`, in a God's-Eye-View / Palantir "night ops" style. There is
no framework or build step. It loads `data.js` (`window.DATA`, built by `dashboard/build_data.py`) and,
from jsDelivr, d3@7.9.0 and topojson-client@3.1.0.

| Area | What it shows |
|---|---|
| Map (center) | US Albers map in Senate / Governor / House modes. States are filled by D win probability at the cursor; House districts are glowing markers (size = volume). Also: settle pulse rings, callouts for the biggest 60-min movers, target brackets, an optional Bluesky volume layer |
| HUD top | Logo, REC clock (ET/UTC), telemetry (markets, posts) |
| Left panel | Chamber mode, layer toggles, control KPIs, CCTV-style wall of the 8 streams |
| Right panel | Kalshi-style time-series card for the selected race (1H/6H/12H/NIGHT/3M). In 3M: poll circles and daily Bluesky bars. Tabs: Contacts, Intercepts (transcripts), Chat, Social (Bluesky: all / from-state / ±60 min / night / since Aug), Search |
| Dock (bottom) | Timeline canvas (control lines, call events, one lane per stream, search hits), transport controls, event jump buttons, NORMAL/NVG/FLIR/CRT presets |

All players seek to the same wall-clock time. `dashboard/index_v1_board.html` is the older table-style
board, kept for reference.

**Run locally:** `.venv/bin/python dashboard/build_data.py && .venv/bin/python dashboard/serve.py 8817`
→ http://localhost:8817/dashboard/index.html. `serve.py` supports HTTP Range requests, which video
seeking needs, and binds to localhost only.

**Hosted build:** `bash dashboard/build_site.sh <out_dir>`. The output dir must be outside any git repo,
or Vercel CLI deploys get blocked. The script:
- cuts ±3 min clips (240p, 15 fps) around each call with `make_clips.py`;
- bundles `data.js` with the clip paths;
- adds `middleware.js` (HTTP basic auth on every path, storing only a SHA-256 of `user:pass`);
- writes `vercel.json` (noindex, no-cache);
- cache-busts `data.js?v=<hash>`.

The deploy is a private, password-protected Vercel project (Hobby plan, 100 MB upload limit, so full
streams are never uploaded). The password lives in a file outside the repo. Never commit it, print it
or put it in code.

## 3. Repo layout
```
collect/    data collection scripts (one per source, see §4)
dashboard/  build_data.py (data -> data.js), index.html (the site), make_clips.py, build_site.sh,
            serve.py (local Range server), shot.py (headless Playwright screenshot check)
data/       ALL downloaded data (git-ignored, ~9.4 GB, lives only on NYU HPC /scratch)
logs/       run logs and private notes (git-ignored)
```

## 4. Data inventory and sources
All paths are relative to `data/`. Sizes and counts are as of 2026-11-13.

Coverage: Senate 34/35 races (Kentucky has no Kalshi market; Alaska is still open), Governor 36/36, House 411/435.

### 4.1 Kalshi prediction markets
- **Source:** Kalshi public trade API v2, `https://api.elections.kalshi.com/trade-api/v2` (no auth).
  Endpoints used: `/series`, `/markets`, `/series/{s}/markets/{t}/candlesticks` (`period_interval` 60 = hourly,
  1 = minute), `/markets/trades`.
- **Ticker map:**

  | Ticker pattern | Market |
  |---|---|
  | `CONTROLS-2026-D/R` | Senate control |
  | `CONTROLH-2026-D/R` | House control |
  | `KXAPCALLHOUSE`, `KXAPCALLSENATE` | AP call timing |
  | `SENATE<ST>` (`SENATE<ST>S` = special), `SENATEPARTY-?<ST>` | Senate races |
  | `HOUSE<ST><N>` (64 districts), `KXHOUSERACE-<ST><N>-26-D/R` (336, one series), `KXHOUSE<ST><N>` (11) | House districts: 411 of 435 in total. The window data adds a `race_series` column that maps all three to `HOUSE<ST><N>` |
  | `GOVPARTY<ST>`, `KXGOV<ST>` | Governors |

| File | Script | Content |
|---|---|---|
| `kalshi/series_elections_politics.json` | `collect/kalshi_collect.py` | Series catalog (7 MB) |
| `kalshi/markets.parquet` | same | 2,405 midterm markets in 196 series; full market fields (`ticker`, `title`, `result`, `volume_fp`, `last_price_dollars`, `settlement_ts`, …) |
| `kalshi/candles/<SERIES>.parquet` | same | Hourly candles, Aug 1 → Nov 12, 1.84 M rows: `ticker, ts, close, mean, bid_close, ask_close, volume, open_interest, time` |
| `window/kalshi/markets.parquet` | `collect/kalshi_window_minute.py` + `collect/kalshi_window_minute_extra.py` | 1,022 markets: control, AP-call, 34 Senate, 36 Gov and 411 House races, plus `race_series` |
| `window/kalshi/minute_candles.parquet` | same | Minute candles in the window, 276,034 rows: `ticker, ts, close, mean, bid, ask, volume` |

### 4.2 Political streamers (YouTube + Twitch)
- **Source:** public channel and VOD pages, accessed with `yt-dlp`. Twitch VODs come from twitch.tv, the
  rest from YouTube.
- **Channels** (`collect/streamer_metadata.py`, `CHANNELS`):

  | Lean | Channels |
  |---|---|
  | Left | Hasan Piker (YouTube @hasanabi + Twitch hasanabi), Destiny, Vaush, Kyle Kulinski (@SecularTalk), Brian Tyler Cohen, The Young Turks |
  | Right | Steven Crowder, Tim Pool (@TimcastIRL), Ben Shapiro / Daily Wire, Charlie Kirk Show |

| File | Script | Content |
|---|---|---|
| `streamers/videos.parquet` / `.csv`, `channels.json` | `collect/streamer_metadata.py` | 3,734 videos since Aug 1, metadata only: `streamer, lean, platform, id, title, upload_date, timestamp, duration_s, view_count, url`. The TYT listing is truncated at ~800 per tab |
| `window/items.json` | `collect/download_window.py` | The 8 election-night streams: `[streamer, lean, platform, id, url]` |
| `window/video/<id>.mp4` | same | 360p video, 9.0 GB total, 50 GB cap. Hasan Twitch `v2918627486` (13.4 h, 3.9 GB), Hasan YT `aO61Eyw-jEs`, BTC `SEqjgdf0EMc`, TYT `yve_Ai2MHGc`, Crowder `EHu5nlFzPLM`, Tim Pool `bG0c5Xzj-70`, Daily Wire `73cHh3h_NJ8`, Kirk `8vy9x-YcOjs` |
| `window/meta/<id>.info.json` | same | yt-dlp info: start time, duration, title |
| `window/chat/<id>.live_chat.json` | same | YouTube live-chat replay, 212 MB. Available for BTC, TYT, Tim Pool and Kirk only |
| `window/captions/<id>.en.json3` | same | YouTube auto-captions, 51 MB |
| `window/transcripts/<id>.json` | `collect/transcribe.py` + `transcribe.sbatch` | `{id, model, segments}`, from Whisper large-v3-turbo (HF transformers) on a SLURM GPU. All 8 streams, ~10.7 k segments |

### 4.3 Bluesky (stand-in for X/Twitter)
- **Source:** Bluesky AppView public API, `https://api.bsky.app/xrpc/app.bsky.feed.searchPosts`
  (`sort=top`), plus `app.bsky.actor.getProfiles` for author bios. No auth.
  - `public.api.bsky.app` and cursor pagination return 403 when unauthenticated, so the scripts take 1 page per
    query and slice by day.
- **Queries:** 337, made of quoted full names of the Kalshi nominees plus `"<State> election"`.
- **Location:** `home_state` is **self-reported**. It is parsed from the profile bio (city names,
  "City, ST", state names). It is not GPS or geotag data.

| File | Script | Content |
|---|---|---|
| `social/bluesky_posts.parquet` | `collect/bluesky_collect.py` | Election-night window, 20,634 rows: `uri, did, handle, name, created, indexed, text, likes, reposts, replies, q, state, kind, event, candidate` |
| `social/bluesky_authors.parquet` | same | 8,137 authors: `did, followers, bio, home_state` (1,686 have a home state) |
| `social/bluesky_daily/YYYY-MM-DD.parquet` | `collect/bluesky_backfill.py` | Day-by-day backfill Aug 1 → Nov 12: 483 k rows, **411,386 unique posts**, all 50 states. Same columns. Resumable |

### 4.4 Polls (general election, since Aug 1)
| Source | Script | Notes |
|---|---|---|
| Wikipedia race pages via the MediaWiki API (`en.wikipedia.org`), CC BY-SA | `collect/polls_wikipedia.py` | Senate (incl. specials), governor and House state pages. Follows split district sub-pages (e.g. California 1–26 / 27–52). Uses "general election" poll tables; nominee columns are matched by last name |
| VoteHub API `https://api.votehub.com/polls`, CC BY 4.0 | `collect/polls_votehub.py` | Raw copy in `polls/raw/votehub_polls.json`. Matched to Kalshi nominees and deduped against Wikipedia (same pollster, ±2 days, D within 1 pt) |

- **Output:** `polls/polls.parquet` / `polls.csv`, 1,628 polls: Senate 722 (23 races), Governor 672 (32), House 234
  (94 of 411 Kalshi districts). Columns: `kind, state, dist, events, page, pollster, end, sample, moe, D_name, R_name,
  D, R, section, source`. `section` flags partisan and internal polls.
- **House polling is genuinely sparse.** 317 of 411 Kalshi districts have no public general-election poll since
  Aug 1; that is a finding, not a bug.
- **Rejected:** ElectIndex `race_polls.csv` (scraped from NYT, no license). Its raw copy is in `polls/raw/`
  but **must not be used or redistributed**.
- 538 shut down in 2025, so it is not a source.

### 4.5 Geography
| File | Source |
|---|---|
| `geo/states-albers-10m.json` | `us-atlas@3.0.1` (jsDelivr), pre-projected Albers USA |
| `geo/cd_gaz.zip` | US Census 2025 Gazetteer, 119th Congress districts (`2025_Gaz_119CDs_national.zip`): district interior points |

Fetched by `collect/fetch_geo.sh`.

### 4.6 Not collected (and why)
| Data | Why not |
|---|---|
| X/Twitter | Recent search only covers 7 days ($0.005/post); full archive is Enterprise (~$42 k/mo). Account timelines (last 3,200 posts) would need a user-supplied paid bearer token |
| Twitch chat replay | Not fetched yet |
| Chat for Crowder, Daily Wire and Hasan's YT stream | No live-chat replay available |
| Reddit | Needs OAuth credentials |

## 5. `data.js` contents (built by `dashboard/build_data.py`, ~14 MB)
| Key | Content |
|---|---|
| `window`, `events` | Window bounds and the call moments |
| `streams` | Video file or clip paths, start offsets |
| `transcripts` | Whisper segments |
| `chats` | Live chat sampled to 12 msgs/min |
| `kalshi` | Minute prices per market, with kind/state/district/party |
| `geo` | Topology + district points `{"ST-N": [lat, lon, sqmi]}` |
| `social` | Night posts: per state top 250 + up to 120 from-state; 10-min counts |
| `long` | 6-hourly Kalshi prices since Aug 1 + polls per race `[t, pollster, D, R, sample]` |
| `social_long` | Daily Bluesky counts by state/race + top 60 posts per state since Aug 1 |

Env vars: `CLIPS_JSON` (use clips instead of full videos), `DATA_OUT` (output path).

## 6. Rules for agents
- **This public repo holds code only.** Never commit or push anything under `data/`, `dashboard/data.js`,
  `deploy_build/`, `logs/`, videos, chat logs, transcripts, Bluesky post text, `.vercel/`, `.env*`, tokens
  or the dashboard password. `.gitignore` covers these; check `git diff --cached --stat` before every commit.
- **Stream videos, chat and transcripts** are third-party copyrighted content collected for private
  research. Share them only privately with the team. Public releases may include aggregates (counts,
  prices, poll tables) and post IDs/URIs, not raw content.
- **Deploying is outward-facing.** Get the owner's OK before each production deploy, and keep the basic-auth
  middleware on every path.
- **Rate limits:** don't try to get around them. Don't use `yt-dlp --impersonate` to beat YouTube 429s; use
  Whisper instead. Throttle Wikipedia, Bluesky and Kalshi requests, and retry with backoff.
- **Compute:** heavy GPU work (Whisper) goes through SLURM (`collect/transcribe.sbatch`), not the login node.
  ffmpeg is the static binary from `imageio-ffmpeg` (`FFMPEG` env).
- **Times:** store UTC epoch seconds; display in America/New_York.
- **Storage:** `data/` sits on HPC `/scratch`, which is **not backed up and is purged**. Back it up before
  relying on it long-term.
