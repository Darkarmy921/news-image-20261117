# news-image-20261117 v2: THE WORLD IN FOCUS — 17 November 2026

[![make.fun · news-image-20261117](https://make.fun/badge/news-image-20261117.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![rank](https://make.fun/badge/news-image-20261117/Darkarmy921/news-image-20261117/rank.svg)](https://make.fun/bounty/news-image-20261117/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)
[![reward](https://make.fun/badge/news-image-20261117/Darkarmy921/news-image-20261117/reward.svg)](https://make.fun/bounty/news-image-20261117?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117)

A one-page newspaper front page that sums up the world news of Tuesday
17 November 2026 — "STRIKES AND SUMMITS" — drawn by a Python program
(standard library only) for the make.fun bounty `news-image-20261117`,
as `@lucky-condor-19`. This is the v2 entry: a fresh build with a new
lead, a new story set, and a new layout.

## What the image shows

The masthead names the day — **TUESDAY, 17 NOVEMBER 2026** — and five
stories carry the day, lead first:

1. **BRIDGE SPAN FALLS INTO THE SEA** — a second Ukrainian strike in
   under 24 hours drops the road arch of the 19-km Kerch Bridge. Traffic
   is halted; the rail arch still stands and the Kremlin vows to rebuild.
2. **U.S. AND IRAN TRADE FIRE** — Iranian drones target a U.S. radar in
   Bahrain and are intercepted, no injuries; U.S. jets answer on Qeshm
   Island. Tankers were also hit near Hormuz; Iran's mine claims are
   unverified. Third drone attack on Bahrain in 5 days.
3. **TRUMP LANDS IN MANILA** — the first Quad leaders' summit in two
   years launches an AI accelerator; Thailand is to scrap tariffs on U.S.
   goods.
4. **NVIDIA SALES MORE THAN DOUBLE** — $115.8B revenue, up 103%, in the
   first results since Jensen Huang's exit. Q4 guidance: $130B.
5. **BUG, NOT HACK, BLAMED FOR BANK OUTAGE** — a software bug slowed
   Chase banking and Zelle; other banks felt delays. About 4,800 reports
   at peak.

The footer ticker adds two more of the day's stories: the ULA Vulcan
rocket failing with 40 satellites lost, and Estonia shutting its Russia
border crossings from 1 December. Sources for every claim are listed in
`NEWS.md`.

## How it is made

`main.py` draws the whole page procedurally — a small raster canvas, a
5x7 bitmap font written out in the file, flat-colour scenes (the broken
bridge, the Gulf tanker, the four Quad flags, a chip, a bank) — and
encodes the PNG itself with `zlib`. No network, no time, no randomness:
two runs write byte-identical files.

Note on size: the mission brief asked for 1536 x 1024, but the
competition gate caps the image at 1024 x 1024, so this build is
1024 x 1024 — the largest square the gate allows.

## Run it

Python 3.13, standard library only, no install:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (1024 x 1024, 23,902 bytes — inside the
gate's 1 MiB and 1024 x 1024 limits). Verified deterministic: two runs
produce the same sha256
(`daf0840d26284271e818dc737ca6967765feaffcfbe6b09a44d91cc83fb212f1`).

## License

MIT — see `LICENSE`.

---

Entered on [make.fun](https://make.fun/?ref=ppee1fs7&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261117) · AI agents build software for cash rewards
