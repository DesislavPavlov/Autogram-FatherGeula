"""Upcoming-captions preview doc for Father Geula posts.

  python posting.py upload --file posting/upcoming.md     create/replace Drive FatherGeula/posting/Upcoming captions
  python posting.py export --out upcoming.txt             current text of that Doc (with Desislav's edits)

Doc format, one block per posting day (only the text between the markers is posted):
  === 2026-11-17 · The Manifesto ===
  <<<CAPTION
  ...
  CAPTION>>>
"""
import argparse, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import drive

DOC_NAME = "Upcoming captions"


def doc_folder():
    return drive.folder(drive.vo_path().rsplit("/", 1)[0] + "/posting")


def cmd_upload(path):
    from googleapiclient.http import MediaFileUpload
    parent = doc_folder()
    existing = drive.child(parent, DOC_NAME)
    for mime in ("text/plain",):
        try:
            media = MediaFileUpload(str(path), mimetype=mime)
            if existing:
                drive.service().files().update(fileId=existing["id"], media_body=media, fields="id").execute()
            else:
                drive.service().files().create(body={"name": DOC_NAME, "parents": [parent], "mimeType": drive.GDOC},
                                               media_body=media, fields="id").execute()
            print("  ↑ posting/" + DOC_NAME)
            return
        except Exception as e:
            if mime == "text/plain":
                raise
            print("  markdown import failed, retrying as plain text:", e)


def cmd_export(out):
    f = drive.child(doc_folder(), DOC_NAME)
    pathlib.Path(out).write_text(drive.export_text(f) if f else "", encoding="utf-8")
    print("exported" if f else "no doc yet")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["upload", "export"])
    ap.add_argument("--file", default="posting/upcoming.md")
    ap.add_argument("--out", default="upcoming.txt")
    a = ap.parse_args()
    cmd_upload(pathlib.Path(a.file)) if a.cmd == "upload" else cmd_export(a.out)
