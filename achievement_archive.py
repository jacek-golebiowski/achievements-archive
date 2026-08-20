#!/usr/bin/env python3
"""
Build a portable gaming-achievement archive from image filenames.

Expected folder layout:
    achievement_archive.py
    completions/
        YYYY-MM-DD__Game Title.jpg
    incomplete/
        YYYY-MM-DD__Game Title.jpg

Example filenames:
    2017-02-09__Murdered Soul Suspect.jpg
    2021-10-20__Halo Infinite.png

Run on macOS with:
    python3 achievement_archive.py --publish

The script reads both folders from the directory containing the script and
writes achievement_archive.html into that same directory.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from config import (
    ARCHIVE_TITLE,
    CLOUDFLARE_PROJECT_NAME,
    GAMERTAG,
    GITHUB_URL,
    PROFILE_IMAGE_NAME,
)


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FILENAME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})__(?P<title>.+)$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class GameEntry:
    title: str
    completed_on: date
    incomplete: bool
    source_path: Path
    output_image_name: str

    @property
    def status(self) -> str:
        return "Incomplete" if self.incomplete else "Completed"

    @property
    def sort_title(self) -> str:
        return self.title.casefold()

    @property
    def iso_date(self) -> str:
        return self.completed_on.isoformat()

    @property
    def display_date(self) -> str:
        return self.completed_on.strftime("%-d %B %Y")


def parse_filename(path: Path, *, incomplete: bool) -> GameEntry:
    match = FILENAME_PATTERN.fullmatch(path.stem)
    if not match:
        raise ValueError("expected YYYY-MM-DD__Game Title.ext")

    try:
        parsed_date = datetime.strptime(match.group("date"), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("invalid calendar date") from exc

    title = match.group("title").strip()
    if not title:
        raise ValueError("game title is empty")

    return GameEntry(
        title=title,
        completed_on=parsed_date,
        incomplete=incomplete,
        source_path=path,
        output_image_name=f"{'incomplete' if incomplete else 'completions'}/{path.name}",
    )


def discover_entries(
    completions_dir: Path,
    incomplete_dir: Path,
) -> tuple[list[GameEntry], list[tuple[Path, str]]]:
    entries: list[GameEntry] = []
    rejected: list[tuple[Path, str]] = []

    for folder, is_incomplete in (
        (completions_dir, False),
        (incomplete_dir, True),
    ):
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)

        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                entries.append(parse_filename(path, incomplete=is_incomplete))
            except ValueError as exc:
                rejected.append((path, str(exc)))

    entries.sort(key=lambda item: (item.completed_on, item.sort_title))
    return entries, rejected


def image_data_uri(path: Path) -> str:
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[path.suffix.lower()]

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_html(
    entries: list[GameEntry],
    output_path: Path,
    *,
    archive_title: str,
    embed_images: bool,
    copied_images_dir: Path | None,
    profile_image_path: Path | None,
) -> None:
    completed_count = sum(not item.incomplete for item in entries)
    incomplete_count = len(entries) - completed_count
    years = sorted({item.completed_on.year for item in entries})
    
    profile_image_html = ""

    if profile_image_path is not None and profile_image_path.exists():
        if embed_images:
            profile_image_src = image_data_uri(profile_image_path)
        else:
            assert copied_images_dir is not None
            profile_output = copied_images_dir / f"profile{profile_image_path.suffix.lower()}"
            shutil.copy2(profile_image_path, profile_output)
            profile_image_src = f"images/{profile_output.name}"

        profile_image_html = f"""
            <section class="profile-section">
                <button
                    class="image-button profile-image-button"
                    type="button"
                    aria-label="Open TrueAchievements profile snapshot"
                >
                    <img
                        src="{profile_image_src}"
                        alt="{html.escape(GAMERTAG)} TrueAchievements profile snapshot"
                    >
                </button>
            </section>
        """
    
    completion_percentage = (
    completed_count / len(entries) * 100
    if entries else 0
)
    
    profile_snapshot = "Not available"
    if profile_image_path is not None and profile_image_path.exists():
        created_timestamp = getattr(
            profile_image_path.stat(),
            "st_birthtime",
            profile_image_path.stat().st_mtime,
        )
        profile_snapshot = datetime.fromtimestamp(created_timestamp).strftime("%-d %B %Y")
    
    cards = []
    for index, item in enumerate(entries):
        if embed_images:
            image_src = image_data_uri(item.source_path)
        else:
            assert copied_images_dir is not None
            image_src = f"images/{item.output_image_name}"

        status_class = "incomplete" if item.incomplete else "completed"

        cards.append(
            f"""
            <article
                class="game-card"
                data-title="{html.escape(item.sort_title, quote=True)}"
                data-game-title="{html.escape(item.title, quote=True)}"
                data-date="{item.iso_date}"
                data-year="{item.completed_on.year}"
                data-status="{status_class}"
                data-completion-status="{status_class}"
            >
                <span class="scraper-status">STATUS: {status_class}</span>
                <button class="image-button" type="button" aria-label="Open {html.escape(item.title)} image">
                    <img
                        src="{image_src}"
                        alt="{html.escape(item.title)} achievement summary"
                        loading="lazy"
                    >
                </button>
            </article>
            """
        )

    year_options = "\n".join(
        f'<option value="{year}">{year}</option>' for year in years
    )

    archive_data = [
        {
            "title": item.title,
            "date": item.iso_date,
            "status": item.status,
            "completion_status": "incomplete" if item.incomplete else "completed",
            "filename": item.source_path.name,
        }
        for item in entries
    ]

    document = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(archive_title)}</title>
    <style>
        :root {{
            color-scheme: dark;
            --background: #0c1723;
            --panel: #142334;
            --panel-hover: #1a2d42;
            --text: #f5f7fa;
            --muted: #aab8c7;
            --border: #2b4157;
            --accent: #9bf000;
            --danger: #ff6b6b;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--background);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}

        header {{
            padding: 22px clamp(18px, 4vw, 56px) 18px;
            background: var(--background);
        }}
        
        .sticky-toolbar {{
            padding: 10px clamp(18px, 4vw, 56px) 16px;

            background: rgba(12, 23, 35, 0.96);
            border-bottom: 1px solid var(--border);
        }}

        .sticky-toolbar .summary {{
            margin-bottom: 12px;
        }}

        h1 {{
            margin: 0 0 6px;
            color: var(--accent);
            font-size: clamp(1.6rem, 4vw, 2.5rem);
        }}

        .summary {{
            margin: 0;
            color: var(--muted);
        }}

        .profile-links {{
            display: flex;
            gap: 14px;
            margin-top: 6px;
            color: var(--muted);
            font-size: 0.9rem;
        }}

        .profile-links a {{
            color: var(--muted);
            text-decoration: underline;
            text-underline-offset: 3px;
        }}

        .profile-links a:hover {{
            color: var(--accent);
            text-decoration: underline;
        }}

        .controls {{
            display: grid;
            grid-template-columns: minmax(180px, 2fr) repeat(3, minmax(145px, 1fr));
            gap: 12px;
            margin-top: 0;
        }}

        label {{
            display: grid;
            gap: 6px;
            color: var(--muted);
            font-size: 0.88rem;
        }}

        input,
        select {{
            width: 100%;
            min-height: 42px;
            padding: 9px 11px;
            color: var(--text);
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 9px;
            font: inherit;
        }}

        main {{
            padding: 26px clamp(18px, 4vw, 56px) 70px;
        }}
        
        .profile-section {{
            width: min(100%, 400px);
            margin: 16px 0 12px;
            text-align: left;
        }}

        .profile-image-button {{
            overflow: hidden;
            border-radius: 18px;
        }}

        .profile-section img {{
            display: block;
            width: 100%;
            height: auto;
        }}

        #empty-state {{
            display: none;
            color: var(--muted);
            text-align: center;
            padding: 80px 20px;
        }}

        #gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 22px;
        }}

        .game-card {{
            position: relative;
            overflow: hidden;
            border-radius: 14px;
            transition: transform 160ms ease;
        }}

        .scraper-status {{
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }}

        .game-card:hover {{
            transform: translateY(-2px);
        }}

        .image-button {{
            position: relative;
            display: block;
            width: 100%;
            padding: 0;
            border: 0;
            background: transparent;
            cursor: zoom-in;
        }}

        .game-card img {{
            display: block;
            width: 100%;
            height: auto;
            background: #08111a;
        }}

        dialog {{
            width: min(95vw, 1500px);
            max-width: none;
            padding: 0;
            overflow: hidden;
            background: #050a10;
            border: 1px solid var(--border);
            border-radius: 12px;
        }}

        dialog::backdrop {{
            background: rgba(0, 0, 0, 0.86);
        }}

        dialog img {{
            display: block;
            max-width: 95vw;
            max-height: 90vh;
            margin: auto;
        }}

        .close-dialog {{
            position: absolute;
            top: 10px;
            right: 10px;
            width: 40px;
            height: 40px;
            color: white;
            background: rgba(0, 0, 0, 0.72);
            border: 1px solid #64748b;
            border-radius: 50%;
            font-size: 1.4rem;
            cursor: pointer;
        }}

        footer {{
            padding: 0 20px 30px;
            color: var(--muted);
            text-align: center;
            font-size: 0.85rem;
        }}

        @media (max-width: 850px) {{
            .controls {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        @media (max-width: 540px) {{
            .controls {{
                grid-template-columns: 1fr;
            }}

            #gallery {{
                grid-template-columns: 1fr;
            }}

            input,
            select {{
                font-size: 16px;
            }}
        }}

        @media print {{
            header {{
                position: static;
            }}

            .controls,
            footer {{
                display: none;
            }}

            body {{
                background: white;
                color: black;
            }}

            #gallery {{
                display: block;
            }}

            .game-card {{
                break-inside: avoid;
                margin-bottom: 20px;
                border: 1px solid #bbb;
                background: white;
            }}

            .game-card img {{
                object-fit: contain;
            }}

            h1 {{
                color: black;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>{html.escape(archive_title)}</h1>
        
        {profile_image_html}
        
        <p class="summary">
            Profile snapshot: {profile_snapshot}
        </p>
        <div class="profile-links">
            <a href="{html.escape(GITHUB_URL, quote=True)}">GitHub</a>
        </div>
        
    </header>
        <div class="sticky-toolbar">
            <p class="summary">
                        <span id="visible-count">{len(entries)}</span> games ·
                        {completed_count} completed ·
                        {incomplete_count} incomplete ·
                        {completion_percentage:.1f}% completion
                    </p>

            <div class="controls">
                <label>
                    Search
                    <input id="search" type="search" placeholder="Game title">
                </label>

                <label>
                    Sort
                    <select id="sort">
                        <option value="date-desc">Newest first</option>
                        <option value="date-asc">Oldest first</option>
                        <option value="title-asc">Title A–Z</option>
                        <option value="title-desc">Title Z–A</option>
                    </select>
                </label>

                <label>
                    Year
                    <select id="year">
                        <option value="all">All years</option>
                        {year_options}
                    </select>
                </label>

                <label>
                    Status
                    <select id="status">
                        <option value="all">All games</option>
                        <option value="completed">Completed</option>
                        <option value="incomplete">Incomplete</option>
                    </select>
                </label>
            </div>
        </div>

    <main>
        <section id="gallery">
            {''.join(cards)}
        </section>
        <p id="empty-state">No games match the selected filters.</p>
    </main>

    <dialog id="image-dialog">
        <button class="close-dialog" type="button" aria-label="Close">×</button>
        <img id="dialog-image" alt="">
    </dialog>

    <footer>
        Generated from image filenames. No metadata file was harmed in the making of this archive.
    </footer>

    <script id="archive-data" type="application/json">{html.escape(json.dumps(archive_data, ensure_ascii=False))}</script>
    <script>
        const gallery = document.querySelector("#gallery");
        const cards = [...document.querySelectorAll(".game-card")];
        const searchInput = document.querySelector("#search");
        const sortSelect = document.querySelector("#sort");
        const yearSelect = document.querySelector("#year");
        const statusSelect = document.querySelector("#status");
        const visibleCount = document.querySelector("#visible-count");
        const emptyState = document.querySelector("#empty-state");
        const dialog = document.querySelector("#image-dialog");
        const dialogImage = document.querySelector("#dialog-image");

        function applyView() {{
            const query = searchInput.value.trim().toLocaleLowerCase();
            const selectedYear = yearSelect.value;
            const selectedStatus = statusSelect.value;

            let visibleCards = cards.filter((card) => {{
                const titleMatches = card.dataset.title.includes(query);
                const yearMatches =
                    selectedYear === "all" ||
                    card.dataset.year === selectedYear;
                const statusMatches =
                    selectedStatus === "all" ||
                    card.dataset.status === selectedStatus;

                return titleMatches && yearMatches && statusMatches;
            }});

            const [sortField, sortDirection] = sortSelect.value.split("-");

            visibleCards.sort((left, right) => {{
                const leftValue = left.dataset[sortField];
                const rightValue = right.dataset[sortField];
                const comparison = leftValue.localeCompare(rightValue);

                return sortDirection === "asc"
                    ? comparison
                    : -comparison;
            }});

            for (const card of cards) {{
                card.hidden = true;
            }}

            for (const card of visibleCards) {{
                card.hidden = false;
                gallery.appendChild(card);
            }}

            visibleCount.textContent = visibleCards.length;
            emptyState.style.display =
                visibleCards.length ? "none" : "block";
        }}

        for (const control of [searchInput, sortSelect, yearSelect, statusSelect]) {{
            control.addEventListener("input", applyView);
            control.addEventListener("change", applyView);
        }}

        document.querySelectorAll(".image-button").forEach((button) => {{
            button.addEventListener("click", () => {{
                const image = button.querySelector("img");
                dialogImage.src = image.src;
                dialogImage.alt = image.alt;
                dialog.showModal();
            }});
        }});

        document.querySelector(".close-dialog").addEventListener("click", () => dialog.close());

        dialog.addEventListener("click", (event) => {{
            if (event.target === dialog) {{
                dialog.close();
            }}
        }});

        applyView();
    </script>
</body>
</html>
"""

    output_path.write_text(document, encoding="utf-8")


def prepare_external_images(entries: list[GameEntry], output_dir: Path) -> Path:
    images_output = output_dir / "images"
    images_output.mkdir(parents=True, exist_ok=True)

    for item in entries:
        destination = images_output / item.output_image_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if item.source_path.resolve() != destination.resolve():
            shutil.copy2(item.source_path, destination)

    return images_output


def build_pdf(entries: list[GameEntry], output_path: Path, archive_title: str) -> None:
    try:
        from PIL import Image, ImageOps
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires Pillow and ReportLab.\n"
            "Install them with:\n"
            "  python3 -m pip install pillow reportlab"
        ) from exc

    page_width, page_height = landscape(A4)
    margin = 28
    header_height = 44
    gap = 18
    slot_height = (page_height - header_height - (2 * margin) - gap) / 2
    slot_width = page_width - (2 * margin)

    canvas = Canvas(str(output_path), pagesize=(page_width, page_height))
    canvas.setTitle(archive_title)

    def draw_header(page_number: int) -> None:
        canvas.setFont("Helvetica-Bold", 16)
        canvas.drawString(margin, page_height - margin + 2, archive_title)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            page_width - margin,
            page_height - margin + 2,
            f"Page {page_number}",
        )

    page_number = 1
    draw_header(page_number)

    for index, item in enumerate(entries):
        slot_index = index % 2
        if slot_index == 0 and index != 0:
            canvas.showPage()
            page_number += 1
            draw_header(page_number)

        top = page_height - margin - header_height - slot_index * (slot_height + gap)
        caption_height = 32
        image_box_height = slot_height - caption_height

        with Image.open(item.source_path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((int(slot_width), int(image_box_height)))

            x = margin + (slot_width - image.width) / 2
            y = top - image.height

            canvas.drawImage(
                ImageReader(image),
                x,
                y,
                width=image.width,
                height=image.height,
                preserveAspectRatio=True,
                mask="auto",
            )

        caption_y = top - image_box_height - 16
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(margin, caption_y, item.title)

        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            page_width - margin,
            caption_y,
            f"{item.display_date} · {item.status}",
        )

    canvas.save()


def write_rejected_log(rejected: Iterable[tuple[Path, str]], output_path: Path) -> None:
    lines = [
        f"{path.name}: {reason}"
        for path, reason in rejected
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish_to_cloudflare(site_dir: Path, project_name: str) -> None:
    """Deploy the generated site with Cloudflare Wrangler."""
    if shutil.which("npx") is None:
        raise RuntimeError(
            "Publishing requires Node.js/npm (the `npx` command was not found).\n"
            "On macOS, install it with: brew install node"
        )

    command = [
        "npx",
        "--yes",
        "wrangler",
        "pages",
        "deploy",
        str(site_dir),
        "--project-name",
        project_name,
    ]
    print(f"Publishing to Cloudflare Pages project: {project_name}")
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static gaming-achievement archive."
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="publish the generated site to Cloudflare Pages with Wrangler",
    )
    parser.add_argument(
        "--project-name",
        default=CLOUDFLARE_PROJECT_NAME,
        help=f"Cloudflare Pages project name (default: {CLOUDFLARE_PROJECT_NAME})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    completions_dir = script_dir / "completions"
    incomplete_dir = script_dir / "incomplete"
    profile_image_path = script_dir / PROFILE_IMAGE_NAME

    entries, rejected = discover_entries(completions_dir, incomplete_dir)

    if not entries:
        print(
            "No valid images found.\n\n"
            "Put images in these folders:\n"
            f"  {completions_dir}\n"
            f"  {incomplete_dir}\n\n"
            "Use filenames such as:\n"
            "  2017-02-09__Murdered Soul Suspect.jpg\n"
            "  2021-10-20__Halo Infinite.png",
            file=sys.stderr,
        )
        return 1

    site_dir = script_dir / "site"
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)

    copied_images_dir = prepare_external_images(entries, site_dir)
    html_path = site_dir / "index.html"
    build_html(
        entries,
        html_path,
        archive_title=ARCHIVE_TITLE,
        embed_images=False,
        copied_images_dir=copied_images_dir,
        profile_image_path=profile_image_path,
    )

    print(f"Created website: {html_path}")
    print(f"Copied {len(entries)} game image(s) into: {copied_images_dir}")

    if rejected:
        rejected_path = script_dir / "rejected_files.txt"
        write_rejected_log(rejected, rejected_path)
        print(
            f"Skipped {len(rejected)} incorrectly named image(s). "
            f"Details: {rejected_path}"
        )

    if args.publish:
        try:
            publish_to_cloudflare(site_dir, args.project_name)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Publish failed: {exc}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
