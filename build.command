#!/bin/bash
set -e
cd "$(dirname "$0")"
python3 achievement_archive.py
printf '\nWebsite generated in: %s/site/index.html\n' "$PWD"
