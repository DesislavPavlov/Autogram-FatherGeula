"""Google Drive I/O for the Father Geula pipeline (OAuth refresh token, no Colab).

Env: GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN
     FG_DRIVE_PATH (default "FatherGeula/VO", relative to My Drive)

  python drive.py pull    --work DIR          in/ + master_prompt.* + character_sheet.* -> DIR
  python drive.py push    --work DIR          out/<job>/, bundles/*, moves processed in/ files
  python drive.py deliver --zip FILE --slug S upload job zip to jobs/, trash S's bundle + kickoff
  python drive.py check                       verify the token and show what's in in/
  python drive.py archive --pattern REGEX     move matching in/ files to in_processed/
  python drive.py status  --work DIR          queue/scripts/ideas/prompts snapshot -> DIR
"""
import argparse, io, json, mimetypes, os, pathlib, sys

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER = "application/vnd.google-apps.folder"
GDOC = "application/vnd.google-apps.document"
_SVC = {}


def service():
    if "svc" not in _SVC:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(None, refresh_token=os.environ["GDRIVE_REFRESH_TOKEN"],
                            client_id=os.environ["GDRIVE_CLIENT_ID"],
                            client_secret=os.environ["GDRIVE_CLIENT_SECRET"],
                            token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
        _SVC["svc"] = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _SVC["svc"]


def _q(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def children(folder_id, folders=None):
    q = f"'{folder_id}' in parents and trashed = false"
    if folders is True:
        q += f" and mimeType = '{FOLDER}'"
    elif folders is False:
        q += f" and mimeType != '{FOLDER}'"
    out, tok = [], None
    while True:
        r = service().files().list(q=q, pageSize=1000, pageToken=tok,
                                   fields="nextPageToken, files(id,name,mimeType,size,modifiedTime)").execute()
        out += r.get("files", [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def child(folder_id, name, create_folder=False):
    q = f"'{folder_id}' in parents and name = '{_q(name)}' and trashed = false"
    hits = service().files().list(q=q, fields="files(id,name,mimeType)").execute().get("files", [])
    if hits:
        return hits[0]
    if not create_folder:
        return None
    return service().files().create(body={"name": name, "mimeType": FOLDER, "parents": [folder_id]},
                                    fields="id,name,mimeType").execute()


def folder(path, create=True):
    fid = "root"
    for part in [p for p in path.split("/") if p]:
        f = child(fid, part, create_folder=create)
        if not f:
            raise SystemExit(f"Drive folder not found: {path} (missing '{part}')")
        fid = f["id"]
    return fid


def vo_path():
    return os.environ.get("FG_DRIVE_PATH", "FatherGeula/VO")


def download(f, dest_dir):
    from googleapiclient.http import MediaIoBaseDownload
    dest_dir.mkdir(parents=True, exist_ok=True)
    name, svc = f["name"], service()
    if f["mimeType"] == GDOC:
        # export native Docs: master prompt -> markdown, scripts -> .docx (the notebook reads both)
        if pathlib.Path(name).stem.lower().startswith("master_prompt"):
            req, name = svc.files().export_media(fileId=f["id"], mimeType="text/markdown"), "master_prompt.md"
        else:
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            req, name = svc.files().export_media(fileId=f["id"], mimeType=mime), pathlib.Path(name).stem + ".docx"
    elif f["mimeType"].startswith("application/vnd.google-apps"):
        print("  skip (Google file type):", name)
        return None
    else:
        req = svc.files().get_media(fileId=f["id"])
    path = dest_dir / name
    with io.FileIO(path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req, chunksize=32 * 1024 * 1024)
        done = False
        while not done:
            _, done = dl.next_chunk()
    print("  ↓", path.relative_to(dest_dir.parent) if dest_dir.parent in path.parents else path)
    return path


def upload(local, parent_id, name=None):
    """Create or overwrite <name> in parent."""
    from googleapiclient.http import MediaFileUpload
    name = name or local.name
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    media = MediaFileUpload(str(local), mimetype=mime, resumable=local.stat().st_size > 5_000_000)
    existing = child(parent_id, name)
    if existing and existing["mimeType"] != FOLDER:
        f = service().files().update(fileId=existing["id"], media_body=media, fields="id").execute()
    else:
        f = service().files().create(body={"name": name, "parents": [parent_id]},
                                     media_body=media, fields="id").execute()
    print("  ↑", name)
    return f["id"]


def upload_tree(local_dir, parent_id):
    for p in sorted(local_dir.iterdir()):
        if p.is_dir():
            upload_tree(p, child(parent_id, p.name, create_folder=True)["id"])
        else:
            upload(p, parent_id)


def trash(file_id):
    service().files().update(fileId=file_id, body={"trashed": True}).execute()


# ---------------------------------------------------------------- commands
def cmd_pull(work):
    vo = folder(vo_path())
    print("Drive:", vo_path())
    for f in children(vo, folders=False):
        stem = pathlib.Path(f["name"]).stem.lower()
        if stem.startswith("master_prompt") or stem == "character_sheet":
            download(f, work)
    in_id = folder(vo_path() + "/in")
    for f in children(in_id, folders=False):
        download(f, work / "in")
    (work / "drive_ids.json").write_text(json.dumps({"vo": vo, "in": in_id,
        "in_files": {f["name"]: f["id"] for f in children(in_id, folders=False)}}, indent=2))


def cmd_push(work):
    ids = json.loads((work / "drive_ids.json").read_text())
    res = json.loads((work / "run_result.json").read_text())
    base = vo_path()
    out_id = folder(base + "/out")
    for d in sorted((work / "out").iterdir()) if (work / "out").exists() else []:
        if d.is_dir():
            upload_tree(d, child(out_id, d.name, create_folder=True)["id"])
    bundles_id = folder(base + "/bundles")
    for b in res["bundles"]:
        upload(work / "bundles" / b["zip"], bundles_id)
        upload(work / "bundles" / b["kickoff_file"], bundles_id)
    done_id = folder(base + "/in_processed")
    by_stem = {pathlib.Path(n).stem.lower(): (n, i) for n, i in ids["in_files"].items()}
    for moved in res["moved"]:
        # .docx we exported from a native Doc maps back to the Doc by stem
        if moved in ids["in_files"]:
            name, fid = moved, ids["in_files"][moved]
        else:
            name, fid = by_stem.get(pathlib.Path(moved).stem.lower(), (None, None))
        if fid:
            service().files().update(fileId=fid, addParents=done_id, removeParents=ids["in"],
                                     fields="id").execute()
            print("  → in_processed/", name)


def cmd_deliver(zip_path, slug):
    base = vo_path()
    upload(zip_path, folder(base + "/jobs"))
    bundles_id = folder(base + "/bundles")
    for name in (f"{slug}_input.zip", f"{slug}_kickoff.txt"):
        f = child(bundles_id, name)
        if f:
            trash(f["id"])
            print("  🗑", name, "(in Drive trash for 30 days)")


def cmd_archive(pattern):
    """Move in/ files whose name matches the regex into in_processed/ (already-made reels)."""
    import re
    base = vo_path()
    in_id, done_id = folder(base + "/in"), folder(base + "/in_processed")
    rx = re.compile(pattern, re.I)
    hits = [f for f in children(in_id, folders=False) if rx.search(f["name"])]
    for f in sorted(hits, key=lambda f: f["name"]):
        service().files().update(fileId=f["id"], addParents=done_id, removeParents=in_id,
                                 fields="id").execute()
        print("  → in_processed/", f["name"])
    left = sorted(f["name"] for f in children(in_id, folders=False))
    print(f"{len(hits)} moved. Still in in/: {', '.join(left) or '(empty)'}")


def export_text(f):
    """Plain text of a Drive file (native Doc -> text/plain, else raw bytes as UTF-8)."""
    svc = service()
    if f["mimeType"] == GDOC:
        data = svc.files().export(fileId=f["id"], mimeType="text/plain").execute()
    elif f["mimeType"].startswith("application/vnd.google-apps"):
        return None
    else:
        data = svc.files().get_media(fileId=f["id"]).execute()
    return data.decode("utf-8-sig", "replace") if isinstance(data, bytes) else data


def _num(name):
    import re
    m = re.match(r"\s*(\d+)\s*[-–—]", name)
    return int(m.group(1)) if m else None


def cmd_status(out_dir):
    """Snapshot for Claude's daily task: queue depth, script approval state, ideas, prompts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    base, root = vo_path(), vo_path().rsplit("/", 1)[0]
    stems = lambda files: sorted({pathlib.Path(f["name"]).stem for f in files})
    in_files = children(folder(base + "/in"), folders=False)
    audio = {pathlib.Path(f["name"]).stem for f in in_files if f["name"].lower().endswith((".mp3", ".wav", ".m4a"))}
    status = {"in_pairs": sorted(s for s in stems(in_files) if s in audio)}
    for state in ("pending", "approved", "rendered"):
        status[f"scripts_{state}"] = stems(children(folder(f"{root}/scripts/{state}"), folders=False))
    known = stems(children(folder(base + "/in_processed"), folders=False)) + stems(in_files) \
        + status["scripts_pending"] + status["scripts_approved"] + status["scripts_rendered"]
    nums = [n for n in map(_num, known) if n is not None]
    status["known_titles"] = sorted(set(known), key=lambda t: (_num(t) or 0, t))
    status["next_number"] = (max(nums) + 1) if nums else 1
    status["queue_days"] = len(status["in_pairs"]) + len(status["scripts_approved"]) + len(status["scripts_pending"])
    root_files = children(folder(root), folders=False)
    ideas = [f for f in root_files if pathlib.Path(f["name"]).stem.lower() == "ideas"]
    status["ideas_file"] = ideas[0]["name"] if ideas else None
    if ideas:
        (out_dir / "ideas.txt").write_text(export_text(ideas[0]) or "", encoding="utf-8")
    pdir = out_dir / "prompts"
    pdir.mkdir(exist_ok=True)
    status["prompts"] = []
    for f in children(folder(root + "/prompts"), folders=False):
        txt = export_text(f)
        if txt is not None:
            name = pathlib.Path(f["name"]).stem + ".md"
            (pdir / name).write_text(txt, encoding="utf-8")
            status["prompts"].append(name)
    (out_dir / "drive_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in status.items() if k != "known_titles"}, ensure_ascii=False, indent=2))


def public_url(file_id):
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def cmd_share(file_id, on=True):
    """Make one video readable by link for Instagram to fetch on its posting day, or undo that."""
    svc = service()
    if on:
        svc.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"},
                                 fields="id").execute()
        print(public_url(file_id))
    else:
        for p in svc.permissions().list(fileId=file_id, fields="permissions(id,type)").execute()["permissions"]:
            if p["type"] == "anyone":
                svc.permissions().delete(fileId=file_id, permissionId=p["id"]).execute()
        print("unshared", file_id)


def cmd_check():
    about = service().about().get(fields="user(emailAddress)").execute()
    print("Token OK for", about["user"]["emailAddress"])
    vo = folder(vo_path(), create=False)
    print(vo_path(), "→", ", ".join(sorted(f["name"] for f in children(vo))))
    print("in/ →", ", ".join(sorted(f["name"] for f in children(folder(vo_path() + "/in"))) ) or "(empty)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["pull", "push", "deliver", "check", "archive", "status", "share", "unshare"])
    ap.add_argument("--work")
    ap.add_argument("--zip")
    ap.add_argument("--slug")
    ap.add_argument("--pattern")
    ap.add_argument("--id")
    a = ap.parse_args()
    if a.cmd == "pull":
        cmd_pull(pathlib.Path(a.work))
    elif a.cmd == "push":
        cmd_push(pathlib.Path(a.work))
    elif a.cmd == "deliver":
        cmd_deliver(pathlib.Path(a.zip), a.slug)
    elif a.cmd in ("share", "unshare"):
        cmd_share(a.id, on=a.cmd == "share")
    elif a.cmd == "status":
        cmd_status(pathlib.Path(a.work))
    elif a.cmd == "archive":
        cmd_archive(a.pattern)
    else:
        cmd_check()
