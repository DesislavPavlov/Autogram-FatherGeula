# Daily Flow-job task (run by Claude's scheduled task)

Runs after `align.yml` (05:17 Sofia). Repo: DesislavPavlov/Autogram-FatherGeula.

1. **Get today's bundle.** `git fetch origin bundles jobs main`, then read `run_result.json` from `origin/bundles`.
   - `created_utc` older than 20 h → the align workflow didn't run. Look at the latest
     "Align VO and build bundle" run (`gh run list -w align.yml -L 1`), notify the reason, stop.
   - `status` = `nothing` → notify "No VO in FatherGeula/VO/in — nothing to build today", stop.
   - `status` = `error` / `failed` → notify the `error` field / the MISMATCH-or-failed job name, stop.
   - If `origin/jobs:job/job.json` already has this bundle's slug → it's done, stop quietly.
2. **Build the job.** Extract `<slug>_input.zip` and act on the `kickoff` message from
   `run_result.json` as if Desislav had pasted it: read `START_HERE.md`, then carry out `MASTER_PROMPT.md`
   exactly, including every validation step it requires, and produce `<slug>_flow_job.zip`.
   Standing rules that always apply, even if the master prompt is older than they are:
   - Father Geula character-sheet shots: write "silent natural breathing" and "silent candle/lamp flicker",
     never "gentle natural breathing" or "flickers softly".
   - Any specific named icon/church/fresco/relic → "REAL FOOTAGE NEEDED" with a generatable fallback.
   - Flow motion prompts: positive phrasing only, no editorial instructions, a fallback prompt for any shot
     with human faces.
   If the master prompt asks a question that needs Desislav's judgment, don't guess: notify him with the
   question and stop.
3. **Deliver.** `git checkout -B jobs origin/main`, put the zip and
   `job/job.json` = `{"slug": "<slug>", "zip": "<slug>_flow_job.zip", "title": "<title>"}` in `job/`,
   commit, `git push --force origin jobs`. The deliver workflow then uploads the zip to
   `FatherGeula/VO/jobs/` and trashes `bundles/<slug>_input.zip` + `<slug>_kickoff.txt` in Drive.
   Check it went green (`gh run list -w deliver.yml -L 1`), retry once if not.
4. **Notify** (push notification): "🎬 Flow job ready: <title> — FatherGeula/VO/jobs/<slug>_flow_job.zip",
   plus the alignment verdict and any warnings in one or two lines.
