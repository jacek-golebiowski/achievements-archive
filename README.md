# ForensicFlubber — Achievement Archive

A personal Xbox achievement archive built around [TrueAchievements]. The project preserves game progress, achievement statistics, and personalized TrueAchievements game-summary images in a searchable, publicly accessible collection.

**Live archive:** [achievement-archive.pages.dev](https://achievement-archive.pages.dev)

## Overview

The project consists of two connected components:

- **Archive website** — A static, responsive gallery and table of games, achievement progress, Gamerscore, TrueAchievements scores, and TA ratios. It features an ordered Trophy Case, sortable columns, search, and status and image filters.
- **TA Show-All Collector** — A Chrome extension that reads the game list from TrueAchievements, updates the archive's JSON database, and downloads game-summary images for new or changed entries.

The website uses an Arctic-blue and pistachio theme and is deployed on Cloudflare Pages.

## How it works

1. The collector reads the expanded **Show all** games table on the TrueAchievements profile and compares the latest achievement counts with the imported `games.json`.
2. **Update** refreshes game metadata and downloads images only for new games, changed earned/total achievement counts, or pending image retries. **Missing Images** targets entries without a successfully archived image.
3. A separate **Sync Trophy Case** action reads the Trophy Case page, records membership and display order, and leaves game images untouched.
4. The collector exports `games.json` and `ta_failures.json`, while downloaded images are stored separately.
5. `achievement_archive.py` builds the static website from the exported database and local image files. The Trophy Case and game library reuse the same archived images.

Image downloads are sequential and throttled to reduce server rate-limit errors. Successful image records are retained if a later refresh fails.

## Repository structure

```text
achievement_archive.py       Website generator and deployment entry point
config.py                    Local configuration
assets/                      Website styles and JavaScript
  style.css
  app.js
ta_showall_extension/       Chrome extension source
favicon.png                  Website favicon
build.command                Build helper
```

The collector's exported database and image directory are local inputs, not required source files in the repository.

## Build and deployment

With the collector export available in the configured local data directory:

```bash
python3 achievement_archive.py
```

The generated static website is written to `site/`.

To build and publish to Cloudflare Pages through Wrangler:

```bash
python3 achievement_archive.py --publish
```

## Data sources

Achievement counts, Gamerscore, TrueAchievements scores, ratios, and Trophy Case ordering originate from [TrueAchievements](https://www.trueachievements.com/). The collection is an independent archival project and is not affiliated with or endorsed by TrueAchievements or Microsoft.
