# Achievements Archive

A small personal archive that builds a static website from my gaming achievement screenshots.

The Python script scans screenshots stored in `completions/` and `incomplete/`, reads the completion date and game title from each filename, and generates a searchable/filterable HTML gallery. It can also publish the generated site directly to Cloudflare Pages.

The screenshots and generated site itself aren't included in this repository.

## Live archive

If you want to browse the actual collection rather than stare at the code:

https://achievement-archive.pages.dev

## Usage

Place screenshots in:

```text
completions/
incomplete/
```

using filenames such as:

```text
2021-10-20__Halo Infinite.png
```

Then run:

```bash
python3 achievement_archive.py
```

To generate and publish the site:

```bash
python3 achievement_archive.py --publish
```

Project-specific values such as the archive title, gamertag, profile image filename, and Cloudflare project name are stored in `config.py`.
