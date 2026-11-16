# Daily task (run by Claude's scheduled task, 06:40 Sofia)

Runs after `align.yml` (05:17). Repo: DesislavPavlov/Autogram-FatherGeula. GitHub via `gh api` REST only.
The `bundles` branch holds today's `run_result.json`, `drive_status.json`, `ideas.txt`, `prompts/*.md`
and the bundle zip. Do **Part A**, then **Part B**, then send **one** notification covering both.

## Part A — today's Flow job

1. Read `run_result.json` from `origin/bundles`.
   - `created_utc` older than 20 h → align didn't run. Check `gh api repos/{o}/{r}/actions/workflows/align.yml/runs?per_page=1`, report why, skip to Part B.
   - `status` = `nothing` → report "no VO in the queue today", skip to Part B.
   - `status` = `error` / `failed` → report the `error` field or the MISMATCH/failed job name, skip to Part B.
   - `origin/jobs:job/job.json` already has this bundle's slug → already done, skip to Part B.
2. Extract `<slug>_input.zip` and act on the `kickoff` message as if Desislav had pasted it: read `START_HERE.md`,
   then carry out `MASTER_PROMPT.md` exactly, including every validation it requires, producing `<slug>_flow_job.zip`.
   Standing rules that always apply, even if the master prompt is older than they are:
   - Father Geula character-sheet shots: "silent natural breathing" and "silent candle/lamp flicker",
     never "gentle natural breathing" or "flickers softly".
   - Any specific named icon/church/fresco/relic → "REAL FOOTAGE NEEDED" with a generatable fallback.
   - Flow motion prompts: positive phrasing only, no editorial instructions, fallback prompt for any shot with human faces.
   If the master prompt needs Desislav's judgment, don't guess: put the question in the notification and skip delivery.
3. `git checkout -B jobs origin/main`, add `job/<slug>_flow_job.zip` and
   `job/job.json` = `{"slug": "<slug>", "zip": "<slug>_flow_job.zip", "title": "<title>"}`, commit,
   `git push --force origin jobs`. Confirm "Deliver Flow job to Drive" went green; retry once if not.

## Part B — keep voiceovers 2 days ahead

1. From `drive_status.json`: `need = max(0, 2 - queue_days)` (`queue_days` = VO pairs in `in/` + approved + pending
   scripts). `need = 0` → skip to the notification, but mention any `scripts_pending` still waiting for approval.
2. Requires `prompts/script_master_prompt.md` on the bundles branch (from Drive `FatherGeula/prompts/`). Missing →
   say so in the notification and skip.
3. For each script needed, numbered from `next_number` upward:
   - **Idea:** the first idea in `ideas.txt` (ideas are separated by blank lines) whose text isn't already in
     `state/used_ideas.json` on main. If none is left, pick one yourself: the content pillar least represented in
     the recent `known_titles`, and a topic none of the `known_titles` already covers.
   - **Write it** exactly as `script_master_prompt.md` specifies (new idea → Job B; a pasted story/testimony →
     Job C with the story verbatim), scored for ElevenLabs v3 audio tags.
   - **Brand rules** (always): no fabricated statistics, testimonials or unverified claims; KJV only, with every
     verse checked word-for-word against two independent sources by web search (if you can't verify it, change
     or remove it); wonders and relics framed as claimed, never certified; the enemy points inward; medical
     topics get a pastoral off-ramp with no numbers; Phase 1 = no product, no WhatsApp, no selling.
   - Save as `scripts_new/<NN> - <TITLE IN CAPS>.md` in this layout (only the marked block goes to ElevenLabs):
     ```
     # <NN> - <TITLE>
     Pillar: <pillar> · Idea: <ideas list | Claude> — <one-line idea>

     ## Script (exactly this goes to ElevenLabs)
     <<<SCRIPT
     <the scored v3 script, tags and ellipses included>
     SCRIPT>>>

     ## On-screen hook options
     ## Verified scripture (reference + sources checked)
     ## Notes and fixes
     ```
     Nothing inside the block may contain ⚠️, VERIFY, [?], TODO or TBD: the renderer refuses those.
4. Add the used ideas' exact text to `state/used_ideas.json` (a JSON list) and push that to `main`. Then
   `git checkout -B scripts origin/main`, add `scripts_new/`, commit, `git push --force origin scripts`.
   Confirm the "Scripts" workflow uploaded them (green run).

## Notification (one push, short)

- 🎬 Today's Flow job: title, `FatherGeula/VO/jobs/<slug>_flow_job.zip`, verdict, and any warnings or questions.
- ✍️ New scripts waiting in `FatherGeula/scripts/pending`: their titles, plus "edit if needed, then move to
  `scripts/approved`; voice renders within 2 hours".
- Anything that blocked a step, stated exactly.
