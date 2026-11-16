"""Run the Father Geula Colab notebook headless (GitHub Actions).

The notebook in notebook/ stays the single source of truth: this runner executes
its cells 2-5 unchanged, except that
  * cell 1 (Colab Drive mount) is replaced by a local folder that drive.py
    has already filled with FatherGeula/VO from Google Drive,
  * a few settings are forced for unattended daily runs (see OVERRIDES),
  * the queue is cut to --max-jobs (default 1 = one reel per day),
  * the Colab-only Drive login used for .gdoc scripts is swapped for the
    OAuth client from drive.py (drive.py already exports Docs to .docx, so
    this is only a fallback).

Writes <work>/run_result.json describing what happened.
"""
import argparse, datetime, json, os, pathlib, re, shutil, sys, traceback

OVERRIDES = {
    "FORCE_REDO": "False",       # never redo; finished inputs are moved away anyway
    "MOVE_WHEN_DONE": "True",    # move processed pairs into in_processed/
    "MAKE_BUNDLES": "True",
    "REBUILD_BUNDLES": "False",
    "PREVIEW_CHARS": "400",
}


def patch_settings(src):
    for name, value in OVERRIDES.items():
        src, n = re.subn(rf"^({name}\s*=\s*)[^#\n]*", rf"\g<1>{value}   ", src, flags=re.M)
        if n == 0:
            print(f"warning: setting {name} not found in cell 2", file=sys.stderr)
    return src


def cell_sources(nb_path):
    nb = json.loads(pathlib.Path(nb_path).read_text(encoding="utf-8"))
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    if len(code) < 5:
        raise SystemExit(f"expected 5 code cells in {nb_path}, found {len(code)}")
    # Drop IPython shell/magic lines in case any are added later.
    clean = lambda s: "\n".join(l for l in s.split("\n") if not l.lstrip().startswith(("!", "%")))
    return [clean(s) for s in code]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, help="local mirror of FatherGeula/VO")
    ap.add_argument("--notebook", default="notebook/Father_Geula_Complete.ipynb")
    ap.add_argument("--max-jobs", type=int, default=1)
    a = ap.parse_args()

    base = pathlib.Path(a.work).resolve()
    dirs = {k: base / v for k, v in
            dict(IN_DIR="in", OUT_DIR="out", DONE_DIR="in_processed", BUNDLE_DIR="bundles").items()}
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(pathlib.Path.home() / ".cache" / "torch"))

    result = {"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "status": "nothing",
              "jobs": [], "problems": [], "bundles": [], "moved": [], "error": None}

    # ---- stand-in for cell 1 ----------------------------------------------
    import torch, torchaudio
    from torchaudio.pipelines import MMS_FA
    g = {"__name__": "__notebook__", "BASE": base, "DRIVE_OK": False,
         "MMS_OK": hasattr(MMS_FA, "get_aligner"), "FFMPEG": shutil.which("ffmpeg"), **dirs}
    print("torch", torch.__version__, "| torchaudio", torchaudio.__version__,
          "| MMS_FA:", g["MMS_OK"], "| ffmpeg:", g["FFMPEG"])
    if not g["MMS_OK"] or not g["FFMPEG"]:
        raise SystemExit("aligner or ffmpeg missing")

    _, c2, c3, c4, c5 = cell_sources(a.notebook)[:5]
    try:
        exec(compile(patch_settings(c2), "cell2_settings", "exec"), g)
        result["problems"] = list(g.get("PROBLEMS", []))
        if len(g["JOBS"]) > a.max_jobs:
            later = g["JOBS"][a.max_jobs:]
            g["JOBS"] = g["JOBS"][:a.max_jobs]
            result["problems"].append(f"{len(later)} more job(s) waiting for later runs: "
                                      + ", ".join(j["audio"].name for j in later))
        result["jobs"] = [{"audio": j["audio"].name, "script": j["script"].name} for j in g["JOBS"]]
        before = {p.name for p in dirs["DONE_DIR"].iterdir()}

        exec(compile(c3, "cell3_engine", "exec"), g)
        try:  # Drive login for .gdoc scripts without Colab
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            import drive
            g["_drive_service"] = drive.service
        except Exception as e:
            print("note: Drive API fallback unavailable:", e)

        if g["JOBS"]:
            exec(compile(c4, "cell4_align", "exec"), g)
        result["moved"] = sorted({p.name for p in dirs["DONE_DIR"].iterdir()} - before)
        exec(compile(c5, "cell5_bundles", "exec"), g)
    except Exception:
        result["status"] = "error"
        result["error"] = traceback.format_exc(limit=4)
        traceback.print_exc()

    for kick in sorted(dirs["BUNDLE_DIR"].glob("*_kickoff.txt")):
        slug = kick.name[: -len("_kickoff.txt")]
        z = dirs["BUNDLE_DIR"] / f"{slug}_input.zip"
        if z.exists():
            result["bundles"].append({"slug": slug, "zip": z.name, "kickoff_file": kick.name,
                                      "kickoff": kick.read_text(encoding="utf-8").strip(),
                                      "mb": round(z.stat().st_size / 1e6, 2)})
    if result["status"] != "error":
        result["status"] = "bundled" if result["bundles"] else ("failed" if result["jobs"] else "nothing")
    (base / "run_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "jobs", "bundles", "problems")}, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
