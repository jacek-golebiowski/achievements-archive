TA SHOW-ALL COLLECTOR v3.4.0
===========================

Install / update
----------------
1. Make a backup of your images folder and your latest known-good games.json.
2. Extract this ZIP into your EXISTING unpacked extension folder (replace the
   old files there, including popup.html, popup.js and background.js).
3. Chrome > chrome://extensions > Developer mode > Reload the EXISTING entry.
   Do not remove the extension entry if you want its stored session backup.

Each synchronization
--------------------
1. Open https://www.trueachievements.com/gamer/ForensicFlubber/games
2. Click Show all.
3. On your FIRST run with no files, check Fresh start. It ignores old
   extension storage, starts with zero game records, and exports a new games.json.
   On EVERY LATER run, select the newest games.json from ta-collector/data/.
   Chrome will not permit an extension to silently open an arbitrary local
   Downloads file.
4. Choose a mode:
   - Missing images only: download games whose database entry does NOT have
     image_download_status=downloaded and a nonempty image_file.
   - New + incomplete: download games whose IDs are NOT in the reference JSON,
     plus existing games whose CURRENT scanned ta_achievements_complete is
     not true. Existing games that just changed from incomplete to complete get a final
     image refresh. Failed final refreshes remain pending for later retries.
5. Press Read JSON & start.
6. Wait for completion (or Stop). The extension exports two files:
   ta-collector/data/games.json
   ta-collector/data/ta_failures.json
   It OVERWRITES those filenames, instead of producing numbered duplicates.
7. On the NEXT RUN, select that newest games.json. Do not reuse an old file.

Rules and safeguards
--------------------
* The explicitly selected games.json is the database reference on every later run.
  Fresh start intentionally uses an empty reference for the very first run.
  Previously stored extension data is NOT used to decide what is new or missing.
* One record per TrueAchievements game ID, with statistics updated from the
  live Show All table and existing archive_completed values preserved.
* A successful final-image refresh clears image_completion_refresh_pending.
  If it fails, this field stays true and New + Incomplete retries next run.
* A successful retry sets image_download_status=downloaded, saves image
  metadata and removes the corresponding error from ta_failures.json.
* A failed attempt cannot erase a previously successful image record.
* Failure file lists only unresolved errors (one per game ID).
* Saved in Chrome storage after each attempted download, and exported at end,
  on Stop, on error, or after five consecutive SERVER_FAILED responses.
* Original v1 sequential download transport, 10-second pause between attempts.
* No Full Refresh mode, no legacy version migration, no sync-state.json.

IMPORTANT: games.json describes the last confirmed download records, but a
browser extension cannot directly inspect arbitrary files on your drive.
Deleting an image manually without changing its downloaded status in
"games.json" may cause Missing Only to skip that game. To force it again,
change its image_download_status to "not_attempted" and image_file to null
in your JSON before choosing it, or use an empty "games" array to start over.

The downloaded image files retain the historical .png filename even where
TrueAchievements responds with image/jpeg. This format quirk is intentionally
unchanged from the original successful download implementation.
