# Autogram — Father Geula

Daily, with no computer involved:

0. **Scripts:** Claude keeps the voiceover queue 2 days ahead. New scripts land in `FatherGeula/scripts/pending`
   as Google Docs. Edit one if needed, then move it to `scripts/approved`. Every 2 hours, `scripts.yml` renders
   approved scripts with ElevenLabs v3 (Natural, speed 0.85) into `FatherGeula/VO/in`. Ideas come from
   `FatherGeula/ideas` (separate ideas with a blank line); when that runs out, Claude picks them itself. The
   writing rules come from `FatherGeula/prompts/script_master_prompt`.

1. **05:17 Sofia: `align.yml`** (GitHub Actions) pulls `FatherGeula/VO/in` from Drive, runs
   `notebook/Father_Geula_Complete.ipynb` headless (one VO+script pair per day), pushes `out/` and the
   bundle back to Drive, moves the pair to `in_processed/`, and publishes the bundle on the `bundles` branch.
2. **Claude's scheduled task** builds the Flow job from the bundle + master prompt (see `DAILY_TASK.md`)
   and force-pushes it to the `jobs` branch.
3. **`deliver.yml`** uploads `<slug>_flow_job.zip` to `FatherGeula/VO/jobs/` and trashes the used bundle +
   kickoff. You get a push notification.

To change the alignment, edit the notebook as usual and commit the new `.ipynb` to `notebook/` —
the runner executes its cells as-is (cell 1's Colab Drive mount is replaced; FORCE_REDO=False,
MOVE_WHEN_DONE=True are forced).

## Setup (once)

1. Google Cloud Console → enable **Google Drive API** → OAuth consent screen (External), add yourself as
   user, then **Publish app → In production** (in *Testing*, refresh tokens die after 7 days).
2. Credentials → Create OAuth client ID → **Desktop app** → download `client_secret.json`.
3. `pip install google-auth-oauthlib && python tools/get_refresh_token.py client_secret.json`,
   sign in as the account that owns `FatherGeula/VO`.
4. Repo → Settings → Secrets and variables → Actions → add `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`,
   `GDRIVE_REFRESH_TOKEN`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`.
5. Actions → "Align VO and build bundle" → Run workflow (first run downloads the 1.2 GB model, ~5 min).
