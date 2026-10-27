# Arctic + Pistachio — Achievement Archive

A self-contained, Cloudflare Pages-ready gaming archive powered by the TA Show-All Collector's `games.json` and downloaded summary images. The old `completions/`, `incomplete/`, profile image, screenshot naming convention and historical completion dates are **not used**.

## Folder layout

Put the collector download folder next to `achievement_archive.py` like this:

```
achievement_archive_arctic/
├── achievement_archive.py
├── config.py
├── assets/
│   ├── style.css
│   └── app.js
├── data/
│   └── games.json               # included preview/fallback database
├── chrome_data_download/
│   └── ta-collector/
│       ├── data/
│       │   ├── games.json       # latest collector export (preferred)
│       │   └── ta_failures.json # not needed by the website
│       └── images/
│           ├── 17944.png
│           └── ...
└── site/                         # generated for hosting
    ├── index.html
    ├── favicon.svg
    ├── assets/
    ├── data/games.json
    └── images/                  # created when images are available
```

Your downloaded folder was named `chrome_data_download/ta-collector` (shown as `CHROME_DATA_DOWNLOAD` in Finder), so the generator automatically searches for either capitalization. **Copy the whole `ta-collector` folder**, keeping its `data/` and `images/` directories, under `chrome_data_download/` next to this script.

If the collector files live elsewhere, use:

```
python3 achievement_archive.py --collector-dir "/full/path/to/ta-collector"
```

The script also checks `ta-collector/` beside itself and under the macOS `~/Downloads` folder. If none are found, it uses the included `data/games.json` only as a demo/preview. It cannot read image files that are still on your own computer until you place them beside the script or pass their location.

## Generate the website

Requires **Python 3.9 or newer**, standard library only; no pip packages needed:

```
python3 achievement_archive.py
```

Or double-click `build.command` on macOS. Open the newly created **`site/index.html`** in a browser. Search, filtering, details and both Gallery/Table views work even as a local file, without a server.

The generator creates the `site/` folder from scratch. **Don't place source images or custom changes in `site/`**: they will be removed on each build. Keep collector originals inside `chrome_data_download/ta-collector`.

### Images and file extensions

The collector saves some real JPEG files with a `.png` filename. This script checks the image signature and exports JPEGs as `.jpg` (or true PNG/WebP when appropriate), preventing broken file types on Cloudflare Pages. The exported JSON contains the correct image paths. No network requests are made to TrueAchievements during generation or viewing the website.

A game whose picture is not downloaded yet gets a blue **Image pending** placeholder; the stats and game card are still displayed. A `downloaded` record whose actual file is missing is reported as a warning, and publishing is blocked unless `--allow-missing-images` is explicitly supplied.

## Publish to Cloudflare Pages

As before, you need Node.js/npm and access to your Cloudflare account through Wrangler. The configured Pages project is `achievement-archive`.

```
python3 achievement_archive.py --publish
```

The script builds the site and then runs Wrangler. It will deploy **the generated `site/` folder**, including the images you've downloaded. You can also upload that folder directly using Cloudflare Pages.

To change the project name:

```
python3 achievement_archive.py --publish --project-name another-project
```

## Updating

1. Let the Chrome extension export its latest `data/games.json` and new images.
2. Make sure they are present in the `chrome_data_download/ta-collector` folder used by the generator.
3. Run `python3 achievement_archive.py` again, or `--publish` to redeploy.

No database migrations or separate completion-date records are required.

## Data and completion semantics

- Game data and totals are derived from the TrueAchievements collector JSON. The collector's `ta_achievements_complete` field is the basis for **100% complete** versus **in progress**. Missing flag = **unverified**.
- `archive_completed`, personal ratings and trophy-case selections are deliberately ignored.
- Weighted achievement completion % = total earned achievements / total listed achievements. Game completion % = share of games marked `ta_achievements_complete: true`.
- Completion dates are not guessed. Games can change from complete to incomplete when DLC adds achievements; rebuild with a newer collector JSON to reflect that change.
- Each static HTML card has `data-completion-status`, `data-ta-achievements-complete`, `data-completion-source="trueachievements"`, and a unique game ID. The public `site/data/games.json` includes the same explicitly labeled status.
- Images are local assets in the deployed website. No Cloudflare/TA image downloads are performed by the website itself.

## Included preview

This package includes the latest uploaded snapshot: **424 games** from October 27, 2026, with downloaded images *not bundled* (you said those are on your computer). The prebuilt `site/` demonstrates the page with placeholders. Rebuild locally with your `chrome_data_download/ta-collector` to include your images.
