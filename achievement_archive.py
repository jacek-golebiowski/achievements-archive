#!/usr/bin/env python3
"""Build and publish the Arctic / Pistachio TrueAchievements archive.

Input: chrome_data_download/ta-collector/data/games.json and
       chrome_data_download/ta-collector/images/<game-id>.png (JPEG inside PNG
       filenames is supported). No old image-filename archive is consulted.

Usage:
  python3 achievement_archive.py
  python3 achievement_archive.py --collector-dir /path/to/ta-collector
  python3 achievement_archive.py --publish
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import CLOUDFLARE_PROJECT_NAME, GITHUB_URL, GAMERTAG

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
VALID_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')
GIF_SIGNATURE = b'GIF8'
ICON = '''<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6.5 8h11a4 4 0 0 1 3.9 3.1l1 5a2.4 2.4 0 0 1-4 2.2l-2.3-2.3H7.9l-2.3 2.3a2.4 2.4 0 0 1-4-2.2l1-5A4 4 0 0 1 6.5 8Z"/><path d="M7.5 11v4M5.5 13h4"/><circle cx="16.5" cy="11.5" r=".7" fill="currentColor" stroke="none"/><circle cx="18" cy="14" r=".7" fill="currentColor" stroke="none"/></svg>'''
SEARCH_ICON = '''<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5"/></svg>'''
GRID_ICON = '''<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>'''
LIST_ICON = '''<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/></svg>'''


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def integer(n: Any) -> str:
    try:
        return f'{int(n):,}'
    except (TypeError, ValueError):
        return '0'


def numeric(n: Any) -> int:
    try:
        return int(n)
    except (TypeError, ValueError):
        return 0


def safe_ratio(n: Any) -> float:
    try:
        x = float(n)
        return x if x == x and abs(x) < 1_000_000 else 0.0
    except (ValueError, TypeError):
        return 0.0


def load_config() -> str:
    return GAMERTAG


def detect_image_type(path: Path) -> str | None:
    """Identify bytes, not filename: Chrome often stores JPEG bytes as .png."""
    try:
        with path.open('rb') as handle:
            signature = handle.read(16)
    except OSError:
        return None
    if signature.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if signature.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if signature.startswith(b'RIFF') and signature[8:12] == b'WEBP':
        return '.webp'
    return None


def find_collector(root: Path, specified: str | None) -> Path | None:
    if specified:
        path = Path(specified).expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f'Collector folder does not exist: {path}')
        return path
    candidates = [
        root / 'chrome_data_download' / 'ta-collector',
        root / 'CHROME_DATA_DOWNLOAD' / 'ta-collector',
        root / 'ta-collector',
        root.parent / 'chrome_data_download' / 'ta-collector',
        root.parent / 'CHROME_DATA_DOWNLOAD' / 'ta-collector',
        root.parent / 'ta-collector',
        Path.home() / 'Downloads' / 'chrome_data_download' / 'ta-collector',
        Path.home() / 'Downloads' / 'CHROME_DATA_DOWNLOAD' / 'ta-collector',
        Path.home() / 'Downloads' / 'ta-collector',
    ]
    for candidate in candidates:
        if (candidate / 'data' / 'games.json').is_file():
            return candidate
    return None


def load_source(root: Path, collector: Path | None) -> tuple[dict[str, Any], Path, Path | None]:
    if collector:
        path = collector / 'data' / 'games.json'
        if not path.is_file():
            raise FileNotFoundError(f'Expected collector database: {path}')
        image_dir = collector / 'images'
    else:
        path = root / 'data' / 'games.json'
        if not path.is_file():
            raise FileNotFoundError('No games.json found. Place chrome_data_download/ta-collector next to this script, or pass --collector-dir.')
        image_dir = None
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('games'), list):
        raise ValueError(f'Expected a TrueAchievements collector JSON with a games list: {path}')
    return data, path, image_dir


def game_image_path(image_dir: Path | None, game_id: int) -> Path | None:
    if image_dir is None:
        return None
    for extension in VALID_IMAGE_EXTENSIONS:
        path = image_dir / f'{game_id}{extension}'
        if path.is_file() and detect_image_type(path):
            return path
    return None


def game_entry(item: dict[str, Any], image_dir: Path | None, output_dir: Path,
               *, should_copy: bool) -> tuple[dict[str, Any], bool]:
    game_id = numeric(item.get('id'))
    if game_id <= 0:
        raise ValueError(f'Invalid game ID: {item.get("id")!r}')
    source_img = game_image_path(image_dir, game_id)
    image_link: str | None = None
    if source_img is not None:
        ext = detect_image_type(source_img)
        assert ext is not None
        image_link = f'images/{game_id}{ext}'
        if should_copy:
            dest = output_dir / image_link
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_img, dest)
    achievements = item.get('achievements') if isinstance(item.get('achievements'), dict) else {}
    gamerscore = item.get('gamerscore') if isinstance(item.get('gamerscore'), dict) else {}
    ta_score = item.get('ta_score') if isinstance(item.get('ta_score'), dict) else {}
    raw_complete = item.get('ta_achievements_complete')
    completion_status = 'completed' if raw_complete is True else 'incomplete' if raw_complete is False else 'unverified'
    earned = numeric(achievements.get('earned'))
    total = numeric(achievements.get('total'))
    percent = round(earned / total * 100, 1) if total else 0
    url = str(item.get('url') or '')
    if not url.startswith('https://www.trueachievements.com/'):
        url = f'https://www.trueachievements.com/gamer/ForensicFlubber/games'
    return ({
        'id': game_id,
        'title': str(item.get('title') or f'Game {game_id}'),
        'completion_status': completion_status,
        'ta_achievements_complete': raw_complete if isinstance(raw_complete, bool) else None,
        'completion_percentage': percent,
        'achievements': {'earned': earned, 'total': total},
        'gamerscore': {'earned': numeric(gamerscore.get('earned')), 'total': numeric(gamerscore.get('total'))},
        'ta_score': {'earned': numeric(ta_score.get('earned')), 'total': numeric(ta_score.get('total'))},
        'ta_ratio': safe_ratio(item.get('ta_ratio')),
        'trophy_case': item.get('trophy_case') is True,
        'trophy_case_position': numeric(item.get('trophy_case_position')) if item.get('trophy_case_position') is not None else None,
        'image_src': image_link,
        'image_download_status': str(item.get('image_download_status') or 'not_attempted'),
        'url': url,
    }, source_img is not None)


def status_text(game: dict[str, Any]) -> str:
    return {'completed': '100% complete', 'incomplete': 'In progress', 'unverified': 'Unverified'}[game['completion_status']]


def card_html(game: dict[str, Any]) -> str:
    title = esc(game['title'])
    game_id = game['id']
    status = game['completion_status']
    p = game['completion_percentage']
    gs = game['gamerscore']['earned']
    ta = game['ta_score']['earned']
    a = game['achievements']
    ratio = f"{game['ta_ratio']:.4f}×"
    if game['image_src']:
        image_html = f'<img src="{esc(game["image_src"])}" alt="TrueAchievements summary for {title}" loading="lazy" decoding="async">'
        body_html = f'<span class="game-body compact-body"><span class="game-title">{title}</span><span class="card-ratio" title="Earned TA ratio">{ratio}</span></span>'
    else:
        image_html = (f'<span class="placeholder placeholder-data"><span class="placeholder-label">IMAGE PENDING</span>'
            f'<span class="placeholder-progress">{p:g}%</span>'
            f'<span class="placeholder-ach">{integer(a["earned"])} / {integer(a["total"])} achievements</span>'
            f'<span class="placeholder-scores">TA {integer(ta)} · GS {integer(gs)}</span></span>')
        body_html = f'<span class="game-body compact-body"><span class="game-title">{title}</span><span class="card-ratio" title="Earned TA ratio">{ratio}</span></span>'
    return f'''<button type="button" class="game-card" data-game-id="{game_id}" data-open-id="{game_id}"
    data-game-title="{title}" data-completion-status="{status}" data-ta-achievements-complete="{str(game['ta_achievements_complete']).lower()}"
    data-completion-source="trueachievements" data-image-available="{str(bool(game['image_src'])).lower()}"
    aria-label="View details for {title}">
      <span class="card-visual">{image_html}</span>
      {body_html}
    </button>'''


def row_html(game: dict[str, Any]) -> str:
    title = esc(game['title'])
    status = game['completion_status']
    a, gs, ta = game['achievements'], game['gamerscore'], game['ta_score']
    tag = f'<span class="table-tag {"complete" if status == "completed" else ""}">{esc(status_text(game))}</span>'
    return (f'<tr data-game-id="{game["id"]}" data-completion-status="{status}" data-ta-achievements-complete="{str(game["ta_achievements_complete"]).lower()}" data-completion-source="trueachievements">'
        f'<td><button class="table-name" type="button" data-open-id="{game["id"]}">{title}</button></td>'
        f'<td>{tag}</td><td class="table-percent">{game["completion_percentage"]:g}%</td>'
        f'<td>{integer(a["earned"])} / {integer(a["total"])}</td>'
        f'<td>{integer(gs["earned"])}</td><td>{integer(ta["earned"])}</td><td>{game["ta_ratio"]:.4f}×</td>'
        f'<td>{"Yes" if game["image_src"] else "—"}</td></tr>')


STAT_ICONS = {
    'Total games': '<rect x="3" y="8" width="18" height="11" rx="5"/><path d="M8 11v5m-2.5-2.5h5M16 12h.01M19 15h.01"/>',
    'Trophy Case': '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4ZM7 6H4v2a4 4 0 0 0 4 4M17 6h3v2a4 4 0 0 1-4 4"/>',
    'Games 100%': '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    'In progress': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
    'Gamerscore': '<path d="m12 2 2.8 6.2 6.8.8-5 4.7 1.3 6.7-5.9-3.2-5.9 3.2 1.3-6.7-5-4.7 6.8-.8Z"/>',
    'TA score': '<path d="M3 18h18M6 15l4-5 4 3 5-8"/><path d="M16 5h3v3"/>',
    'TA ratio': '<path d="M4 20 20 4M5 5h6v6H5zM13 13h6v6h-6z"/>',
    'Achievements': '<circle cx="12" cy="8" r="5"/><path d="m8 13-2 9 6-3 6 3-2-9"/>',
}

def stat_html(label: str, value: str, sub: str) -> str:
    symbol = STAT_ICONS.get(label,'')
    icon = f'<svg class="stat-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{symbol}</svg>'
    return (f'<article class="stat"><div class="stat-top">{icon}<span class="stat-label">{esc(label)}</span></div>'
            f'<strong class="stat-value">{esc(value)}</strong></article>')


def trophy_tile(game: dict[str, Any]) -> str:
    title=esc(game['title'])
    if game['image_src']:
        visual=f'<img src="{esc(game["image_src"])}" alt="{title} achievement summary" loading="lazy" decoding="async">'
    else:
        visual=f'<span class="trophy-placeholder">{ICON}</span>'
    return f'<button type="button" class="trophy-tile" data-open-id="{game["id"]}" title="{title}" aria-label="View {title}"><span class="trophy-art">{visual}</span><span class="trophy-name">{title}</span></button>'


def timestamp_label(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return 'unknown'
    try:
        dt = datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
        return dt.strftime('%d %b %Y, %H:%M UTC')
    except ValueError:
        return 'unknown'


def build_html(data: dict[str, Any], games: list[dict[str, Any]], missing_count: int) -> str:
    gamertag = load_config()
    count = len(games)
    total_complete = sum(g['completion_status'] == 'completed' for g in games)
    total_incomplete = sum(g['completion_status'] == 'incomplete' for g in games)
    total_unknown = count - total_complete - total_incomplete
    total_images = sum(bool(g['image_src']) for g in games)
    total_ach = sum(g['achievements']['earned'] for g in games)
    total_ach_possible = sum(g['achievements']['total'] for g in games)
    total_gs = sum(g['gamerscore']['earned'] for g in games)
    total_gs_possible = sum(g['gamerscore']['total'] for g in games)
    total_ta = sum(g['ta_score']['earned'] for g in games)
    total_ta_possible = sum(g['ta_score']['total'] for g in games)
    percentage = 100.0 * total_complete / count if count else 0
    achievements_pct = 100.0 * total_ach / total_ach_possible if total_ach_possible else 0
    update = timestamp_label(data.get('exported_at'))
    trophy_games = sorted((g for g in games if isinstance(g['trophy_case_position'], int) and g['trophy_case_position'] > 0), key=lambda g: (g['trophy_case_position'],g['id']))
    trophy_count = len(trophy_games)
    overall_ratio = total_ta / total_gs if total_gs else 0.0
    stats = ''.join([
        stat_html('Total games', integer(count), ''),
        stat_html('Games 100%', integer(total_complete), ''),
        stat_html('TA ratio', f'{overall_ratio:.4f}×', ''),
        stat_html('TA score', integer(total_ta), ''),
        stat_html('Gamerscore', integer(total_gs), ''),
        stat_html('Achievements', integer(total_ach), ''),
    ])
    trophy_markup = '\n'.join(trophy_tile(g) for g in trophy_games)
    if not trophy_markup:
        trophy_markup = '<p class="trophy-empty">Trophy Case order not synced yet. Open your Trophy Case in Chrome and use Sync Trophy Case in the TA Collector extension, then regenerate this site.</p>'
    json_payload = json.dumps({'games': games}, ensure_ascii=False, separators=(',', ':'))
    json_payload = json_payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    game_cards = '\n'.join(card_html(g) for g in games)
    rows = '\n'.join(row_html(g) for g in games)
    source_url = 'https://www.trueachievements.com/gamer/ForensicFlubber'
    return f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#06172e">
<meta name="description" content="{esc(gamertag)}'s Xbox achievements, TrueAchievements score, Gamerscore and game completion gallery.">
<title>{esc(gamertag)} — Achievement Archive</title>
<link rel="icon" href="favicon.png" type="image/png">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="site-header"><nav class="container nav" aria-label="Main navigation">
  <a class="brand" href="#top" aria-label="Achievement Archive home"><span class="brand-mark">{ICON}</span><span><span class="brand-name">{esc(gamertag.upper())}</span><span class="brand-subtitle">ACHIEVEMENT ARCHIVE</span></span></a>
  <div class="nav-links"><a class="nav-link" href="{esc(source_url)}" target="_blank" rel="noopener noreferrer">{ICON}<span>TrueAchievements</span></a><a class="nav-link" href="{esc(GITHUB_URL)}" target="_blank" rel="noopener noreferrer">&lt;/&gt;<span>GitHub</span></a></div>
</nav></header>
<main id="top" class="container">
<section class="trophy-section" aria-labelledby="trophy-title">
  <div class="trophy-heading"><div><h1 id="trophy-title">Trophy Case</h1></div><a class="trophy-external" href="https://www.trueachievements.com/gamer/ForensicFlubber/trophycase" target="_blank" rel="noopener noreferrer">View on TA ↗</a></div>
  <div class="trophy-grid">{trophy_markup}</div>
</section>
<section class="stats" aria-label="Achievement overview">{stats}</section>

<section class="library" aria-labelledby="library-title"><div class="section-heading">
  <div><h2 class="section-title" id="library-title">Game Library</h2><p class="library-source">Source: <a href="{esc(source_url)}" target="_blank" rel="noopener noreferrer">TrueAchievements</a> · Updated {esc(update)}</p></div>
  <div class="view-switch" role="group" aria-label="Choose library layout"><button class="view-btn is-active" aria-pressed="true" type="button" data-view="gallery">{GRID_ICON} Gallery</button><button class="view-btn" aria-pressed="false" type="button" data-view="table">{LIST_ICON} Table</button></div>
</div>
<div class="filters" aria-label="Filter and sort games">
  <label class="field search-field"><span class="field-label">SEARCH GAMES</span><span class="input-wrap">{SEARCH_ICON}<input id="search" type="search" placeholder="Search by title..." autocomplete="off"></span></label>
  <div class="button-filter"><span class="field-label">ACHIEVEMENT STATUS</span><div class="filter-actions" role="group" aria-label="Achievement status"><button type="button" class="filter-btn is-active" data-filter-status="all" aria-pressed="true">All games</button><button type="button" class="filter-btn" data-filter-status="completed" aria-pressed="false">Complete</button><button type="button" class="filter-btn" data-filter-status="incomplete" aria-pressed="false">In progress</button></div></div>
  <div class="button-filter"><span class="field-label">IMAGES</span><div class="filter-actions" role="group" aria-label="Image availability"><button type="button" class="filter-btn is-active" data-filter-image="all" aria-pressed="true">All</button><button type="button" class="filter-btn" data-filter-image="available" aria-pressed="false">Archived</button><button type="button" class="filter-btn" data-filter-image="missing" aria-pressed="false">Missing</button></div></div>
  <label class="field sort-field"><span class="field-label">SORT BY</span><span class="select-wrap"><select id="sort"><option value="ratio-desc" selected>TA ratio (highest)</option><option value="ta-desc">TA score (highest)</option><option value="gs-desc">Gamerscore (highest)</option><option value="ach-desc">Achievements earned</option><option value="completion-desc">Completion (highest)</option><option value="completion-asc">Completion (lowest)</option><option value="title-asc">Title A–Z</option><option value="title-desc">Title Z–A</option></select></span></label>
</div>
<div class="library-meta"><span class="results-line"><strong id="result-count">{integer(count)}</strong> games shown</span><button class="clear-btn" type="button" id="clear-filters" hidden>Clear filters</button></div>
<div class="gallery" id="gallery" aria-label="Game gallery">{game_cards}</div>
<div class="table-wrap" id="table-view" hidden><table class="game-table"><thead><tr><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="title" aria-label="Sort by Game">Game<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="status" aria-label="Sort by Status">Status<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="completion" aria-label="Sort by Progress">Progress<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="ach" aria-label="Sort by Achievements">Achievements<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="gs" aria-label="Sort by Gamerscore">Gamerscore<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="ta" aria-label="Sort by TA score">TA score<span class="sort-indicator" aria-hidden="true">↕</span></button></th><th scope="col" aria-sort="descending"><button class="column-sort" type="button" data-sort-column="ratio" aria-label="Sort by TA ratio">TA ratio<span class="sort-indicator" aria-hidden="true">↓</span></button></th><th scope="col" aria-sort="none"><button class="column-sort" type="button" data-sort-column="image" aria-label="Sort by Image">Image<span class="sort-indicator" aria-hidden="true">↕</span></button></th></tr></thead><tbody id="table-body">{rows}</tbody></table></div>
<div class="empty" id="empty-state" hidden><strong>No games found</strong>Try changing the search or filters.</div>
</section></main>
<dialog id="detail-dialog" class="detail-dialog" aria-labelledby="detail-title"><div class="dialog-inner">
  <div class="dialog-head"><div><p class="dialog-status" id="detail-status"></p><h2 class="dialog-title" id="detail-title"></h2></div><button type="button" class="dialog-close" id="detail-close" aria-label="Close details">×</button></div>
  <div class="dialog-image" id="detail-image"></div><div class="dialog-details" id="detail-metrics"></div>
  <div class="dialog-actions"><span class="dialog-note" id="detail-note"></span><a class="external-btn" id="detail-link" href="{esc(source_url)}" target="_blank" rel="noopener noreferrer">View on TrueAchievements ↗</a></div>
</div></dialog>
<script type="application/json" id="archive-data">{json_payload}</script>
<script src="assets/app.js" defer></script>
</body></html>'''


def make_site(args: argparse.Namespace) -> tuple[Path, dict[str, int]]:
    collector = find_collector(ROOT, args.collector_dir)
    data, source, img_dir = load_source(ROOT, collector)
    print(f'Reading games from {source}')
    if img_dir:
        print(f'Reading images from {img_dir}')
    else:
        print('No local image folder found: preview will display image placeholders.')
    dest = Path(args.output_dir).expanduser().resolve() if args.output_dir else ROOT / 'site'
    if dest == ROOT or dest == collector or dest == img_dir or (dest in ROOT.parents):
        raise ValueError(f'Unsafe output directory: {dest}')
    if dest.exists():
        shutil.rmtree(dest)
    (dest / 'assets').mkdir(parents=True, exist_ok=True)
    (dest / 'data').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ASSETS / 'style.css', dest / 'assets' / 'style.css')
    shutil.copy2(ASSETS / 'app.js', dest / 'assets' / 'app.js')
    records, seen = [], set()
    expected = 0
    missing_expected: list[dict[str,Any]] = []
    for item in data['games']:
        if not isinstance(item, dict):
            raise ValueError('Every game record must be a JSON object')
        game, found = game_entry(item, img_dir, dest, should_copy=True)
        if game['id'] in seen:
            raise ValueError(f'Duplicate game ID: {game["id"]}')
        seen.add(game['id'])
        records.append(game)
        if game['image_download_status'] == 'downloaded':
            expected += 1
            if not found:
                missing_expected.append(game)
    records.sort(key=lambda g: (-g['ta_ratio'],g['title'].casefold()))
    (dest / 'index.html').write_text(build_html(data, records, len(missing_expected)),encoding='utf-8')
    (dest / 'data' / 'games.json').write_text(json.dumps({'source':data.get('source'),'exported_at':data.get('exported_at'),'completion_source':'ta_achievements_complete','games':records},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    favicon = ROOT / 'favicon.png'
    if favicon.is_file():
        shutil.copy2(favicon, dest / 'favicon.png')
    else:
        print(f'WARNING: favicon.png not found at {favicon}; no favicon was copied.', file=sys.stderr)
    totals = {'games':len(records),'images':sum(bool(g['image_src']) for g in records),'expected_images':expected,'missing_expected_images':len(missing_expected),'complete':sum(g['completion_status']=='completed' for g in records)}
    print(f'Created {dest / "index.html"} ({totals["games"]} games; {totals["complete"]} TA-complete; {totals["images"]} actual images)')
    if missing_expected:
        print(f'WARNING: {len(missing_expected)} game(s) marked downloaded in JSON lack local image files.',file=sys.stderr)
        for g in missing_expected[:8]:
            print(f'  - {g["id"]}: {g["title"]}',file=sys.stderr)
        if len(missing_expected)>8:
            print(f'  (+ {len(missing_expected)-8} more)',file=sys.stderr)
    return dest, totals


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description='Build the Arctic + Pistachio Xbox Achievement Archive')
    parser.add_argument('--collector-dir',help='Path to ta-collector (containing data/games.json and images/)')
    parser.add_argument('--output-dir',help='Output directory (default: site/)')
    parser.add_argument('--publish',action='store_true',help='Deploy generated site to Cloudflare Pages with Wrangler (requires Node/npm)')
    parser.add_argument('--allow-missing-images',action='store_true',help='Permit publishing even if downloaded image records do not have matching local files')
    parser.add_argument('--project-name',default=CLOUDFLARE_PROJECT_NAME,help='Cloudflare Pages project name')
    return parser.parse_args()


def main() -> int:
    args=parse_args()
    try:
        output,totals=make_site(args)
        if args.publish:
            if totals['missing_expected_images'] and not args.allow_missing_images:
                print('Not publishing: some recorded downloaded images are absent. Supply the complete chrome_data_download/ta-collector folder or use --allow-missing-images.',file=sys.stderr)
                return 2
            if not shutil.which('npx'):
                print('Publishing needs Node.js/npm (npx not found). Install Node.js first.',file=sys.stderr)
                return 2
            command=['npx','--yes','wrangler','pages','deploy',str(output),'--project-name',args.project_name]
            print(f'Publishing to Cloudflare Pages project {args.project_name} ...')
            subprocess.run(command,check=True)
        return 0
    except (OSError,ValueError,json.JSONDecodeError,subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
