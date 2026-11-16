# Daily posting task (Claude's scheduled task, 08:40 Sofia, every day except Saturday)

Instagram account: **father.geula** via the Windsor.ai connector (`instagram`, account `17841435561558550`).
Windsor publishes immediately, so this task *is* the schedule: one Reel per day, never on Saturday.
GitHub via `gh api` REST only. Queue: `state/post_queue.json` on main.

## 1. Pick today's reel
- Today is Saturday (Europe/Sofia) → stop, no notification.
- `queue` is in posting order. Today's reel = the first entry with `status: "queued"`.
- **Gates:** if that entry has a `gate`, post it only once Desislav has confirmed in reply to a notification
  (for example "Brotherhood is open"). Starting 3 posting days before it, ask in every notification. If it's
  still unconfirmed on the day, post nothing, keep the queue as is, and ask again. Entries with a `note`:
  follow it (for example, remind him the day before).
- An entry with `file_id: null` (a reel not made yet): look it up by title in the reels folder. If it isn't
  there yet, post nothing and say so.
  If an entry already has `posted_on` = today, today is done → skip to step 5.
- **New reels:** list the reels folder (`reels_folder_id`) with the Google Drive connector. Every `.mp4` whose
  file id isn't in the queue gets appended at the end (`status: "queued"`), oldest first. Ignore `.archive`
  and `.meta`.

## 2. Caption
- Export the preview doc: dispatch `posting.yml` with `command=export`, wait for it, and read the doc text
  from the run log. Or read Drive `FatherGeula/posting/Upcoming captions` with the Drive connector.
  If today's block (`=== <YYYY-MM-DD> · <title> ===` … `<<<CAPTION` … `CAPTION>>>`) exists, post **that text
  exactly**, because Desislav may have edited it.
- Otherwise, write it now with the steps below.
- **Writing a caption:** follow `prompts/publishing_master_prompt.md` (on the `bundles` branch; Drive
  `FatherGeula/prompts/` if missing). Base it on the reel's actual script. Look for the script in this order:
  `FatherGeula/VO/in_processed/<title>.txt`, `FatherGeula/scripts/rendered/`, the "Father Geula - Scripts
  Revised" Doc, then the reel's zip in the reels folder's `.archive`.
  - Derive keywords fresh from the script, and use 3–5 hashtags.
  - Follow the brand rules: no fabricated claims, KJV only, wonders framed as claimed, no product or selling
    (Phase 1).
  - Max 2,200 characters.
  - If no script can be found, write from the title only, and flag that in the notification.

## 3. Post
1. Dispatch `posting.yml` with `command=share` and `file_id=<reel id>`, and wait for it to finish green.
   Its log must show `check: http 200 type video/mp4`; if not, unshare, mark the entry `failed` with the
   reason, notify, and stop.
2. Windsor `execute_action`: connector `instagram`, account `17841435561558550`, action `create_video_post`,
   params `{"video_url": "https://drive.usercontent.google.com/download?id=<id>&export=download&confirm=t",
   "caption": <caption>, "share_to_feed": true}`.
   Then post the day's `FIRST_COMMENT` block (the hashtags) with `create_comment` on the new media id.
   The publishing prompt keeps hashtags out of the caption body.
3. **Always** dispatch `posting.yml` `command=unshare` for that file afterwards, success or not.
4. If the post fails, retry once. Mark the entry `failed` with the error only if the retry fails too. Never
   post the same reel twice: before retrying, check with Windsor `get_data` (instagram media for today)
   that it didn't go up.

## 4. Record
- Set the entry to `status: "posted"`, `posted_on: <today>`, `media_id`, `caption`.
- Commit `state/post_queue.json` to main and push.

## 5. Refresh the preview doc
- Build `posting/upcoming.md` for the next 3 posting days after today, skipping Saturdays, from the queue order.
- Keep any existing block for those dates **verbatim**, since it may contain edits. Write captions only for
  dates without a block.
- Each block: `=== <date> · <title> ===`, then `<<<CAPTION` … `CAPTION>>>`, then `<<<FIRST_COMMENT` hashtags `FIRST_COMMENT>>>`.
- Add a header line: "Edit any caption between the markers. Whatever is here at 08:40 on its day gets posted.
  Saturdays are skipped."
- Then run `git checkout -B posting origin/main`, add the file, commit, `git push --force origin posting`, and
  confirm the run went green.

## 6. Notify (one short push)
"📲 Posted: <title>" with the Instagram link if Windsor returns one, then the next 3 titles with their dates.
Include anything that failed, stated exactly.
