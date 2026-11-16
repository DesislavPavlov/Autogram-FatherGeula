"""Script approval + ElevenLabs rendering for Father Geula.

Drive layout (next to FatherGeula/VO):
  FatherGeula/scripts/pending/    new scripts from Claude, as Google Docs — edit freely
  FatherGeula/scripts/approved/   move a Doc here to approve it
  FatherGeula/scripts/rendered/   voiced scripts (kept for the publishing step)

Only the text between the <<<SCRIPT and SCRIPT>>> lines is sent to ElevenLabs.

  python scripts.py upload-pending --dir scripts_new     Claude's new .md scripts -> pending/ as Docs
  python scripts.py render                               approved/ -> ElevenLabs v3 -> VO/in/<name>.mp3 + .txt

Env for render: ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
  optional ELEVENLABS_MODEL (eleven_v3), ELEVENLABS_STABILITY (0.5 = Natural), ELEVENLABS_SPEED (0.85)
"""
import argparse, json, os, pathlib, re, sys, tempfile, urllib.error, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import drive

START, END = "<<<SCRIPT", "SCRIPT>>>"
BLOCKERS = re.compile(r"⚠️|\bVERIFY\b|\[\?\]|\bTODO\b|\bTBD\b")


def root():
    return drive.vo_path().rsplit("/", 1)[0]


def extract(text):
    s, e = text.find(START), text.find(END)
    if s < 0 or e < 0 or e < s:
        raise ValueError(f"no {START} … {END} block")
    body = text[s + len(START):e].strip("\n")
    body = "\n".join(l.rstrip() for l in body.splitlines()).strip()
    if not body:
        raise ValueError("script block is empty")
    hit = BLOCKERS.search(body)
    if hit:
        raise ValueError(f"script block still contains “{hit.group(0)}” — resolve it, then re-approve")
    if len(body) > 5000:
        raise ValueError(f"script is {len(body)} characters; eleven_v3 accepts at most 5,000")
    return body


def cmd_upload_pending(src):
    from googleapiclient.http import MediaFileUpload
    pending = drive.folder(root() + "/scripts/pending")
    for p in sorted(src.glob("*.md")):
        extract(p.read_text(encoding="utf-8"))          # refuse to upload a malformed script
        name = p.stem
        if drive.child(pending, name):
            print("  exists, skipped:", name)
            continue
        for mime in ("text/markdown", "text/plain"):
            try:
                drive.service().files().create(
                    body={"name": name, "parents": [pending], "mimeType": drive.GDOC},
                    media_body=MediaFileUpload(str(p), mimetype=mime), fields="id").execute()
                print("  ↑ scripts/pending/", name)
                break
            except Exception as e:
                if mime == "text/plain":
                    raise
                print("  markdown import failed, retrying as plain text:", e)


def tts(text):
    key, voice = os.environ["ELEVENLABS_API_KEY"], os.environ["ELEVENLABS_VOICE_ID"]
    hdr = {"xi-api-key": key, "Content-Type": "application/json"}
    settings = {}
    try:  # start from the voice's saved settings, then pin what the brand locks
        req = urllib.request.Request(f"https://api.elevenlabs.io/v1/voices/{voice}/settings", headers=hdr)
        settings = json.load(urllib.request.urlopen(req, timeout=30))
    except Exception as e:
        print("  note: couldn't read saved voice settings:", e)
    settings["stability"] = float(os.environ.get("ELEVENLABS_STABILITY") or 0.5)
    settings["speed"] = float(os.environ.get("ELEVENLABS_SPEED") or 0.85)
    body = json.dumps({"text": text, "model_id": os.environ.get("ELEVENLABS_MODEL") or "eleven_v3",
                       "voice_settings": settings}).encode()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
    req = urllib.request.Request(url, data=body, headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.read(), r.headers.get("x-character-count")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ElevenLabs {e.code}: {e.read()[:400].decode('utf-8', 'replace')}")


def cmd_render(result_path):
    r = root()
    approved, rendered = drive.folder(r + "/scripts/approved"), drive.folder(r + "/scripts/rendered")
    in_id = drive.folder(drive.vo_path() + "/in")
    result = {"rendered": [], "skipped": []}
    for f in sorted(drive.children(approved, folders=False), key=lambda f: f["name"]):
        name = pathlib.Path(f["name"]).stem if f["mimeType"] != drive.GDOC else f["name"]
        try:
            script = extract(drive.export_text(f) or "")
            if drive.child(in_id, name + ".mp3"):
                raise ValueError("VO/in already has this mp3")
            audio, chars = tts(script)
            with tempfile.TemporaryDirectory() as td:
                mp3, txt = pathlib.Path(td) / f"{name}.mp3", pathlib.Path(td) / f"{name}.txt"
                mp3.write_bytes(audio)
                txt.write_text(script + "\n", encoding="utf-8")
                drive.upload(txt, in_id)      # script first, so align never sees a lone mp3
                drive.upload(mp3, in_id)
            drive.service().files().update(fileId=f["id"], addParents=rendered, removeParents=approved,
                                           fields="id").execute()
            result["rendered"].append({"name": name, "characters": chars, "kb": len(audio) // 1024})
            print(f"  🎙 {name}: {chars} characters, {len(audio) // 1024} KB → VO/in")
        except Exception as e:
            result["skipped"].append({"name": name, "why": str(e)})
            print(f"  ✗ {name}: {e}")
    pathlib.Path(result_path).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result["rendered"] and not result["skipped"]:
        print("Nothing approved.")
    return 1 if result["skipped"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["upload-pending", "render"])
    ap.add_argument("--dir", default="scripts_new")
    ap.add_argument("--result", default="render_result.json")
    a = ap.parse_args()
    if a.cmd == "upload-pending":
        cmd_upload_pending(pathlib.Path(a.dir))
    else:
        sys.exit(cmd_render(a.result))
