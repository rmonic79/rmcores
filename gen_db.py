#!/usr/bin/env python3
"""
Genera db.json.zip per il Downloader del MiSTer (custom database).

Scandisce _Arcade/ e produce il JSON con percorsi, MD5 e dimensioni, poi lo
zippa. Schema: MiSTer-devel/Downloader_MiSTer, docs/custom-databases.md.

Uso:
  python gen_db.py <sha_commit>

Il commit e' quello del ramo che CONTIENE i file (non il ramo db): finisce in
base_files_url, cosi' gli URL puntano a una revisione fissa e non cambiano
sotto i piedi degli utenti mentre scaricano.
"""
import hashlib, json, os, sys, time, zipfile

DB_ID = "rmonic79/rmcores"
REPO  = "rmonic79/rmcores"
ROOT  = os.path.dirname(os.path.abspath(__file__))

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()

def main():
    if len(sys.argv) != 2:
        print(__doc__); return 1
    sha = sys.argv[1]
    files, folders = {}, {}
    for dp, dn, fn in os.walk(os.path.join(ROOT, "_Arcade")):
        for f in fn:
            full = os.path.join(dp, f)
            rel  = os.path.relpath(full, ROOT).replace(os.sep, "/")
            entry = {"hash": md5(full), "size": os.path.getsize(full)}
            # tangle: gli RBF sono datati, quindi se il nuovo non si scarica
            # quello vecchio NON va cancellato, o il core sparisce.
            if rel.endswith(".rbf"):
                base = os.path.basename(rel).split("_")[0].lower()
                entry["tangle"] = [base + "_core"]
            files[rel] = entry
            d = os.path.dirname(rel)
            while d and d not in folders:
                folders[d] = {}
                d = os.path.dirname(d)
    db = {
        "v": 1,
        "db_id": DB_ID,
        "timestamp": int(time.time()),
        "base_files_url": "https://raw.githubusercontent.com/%s/%s/" % (REPO, sha),
        "files": files,
        "folders": dict(sorted(folders.items())),
    }
    out_json = os.path.join(ROOT, "db.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=1, ensure_ascii=False, sort_keys=True)
    with zipfile.ZipFile(os.path.join(ROOT, "db.json.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out_json, "db.json")
    print("%d file, %d cartelle -> db.json.zip" % (len(files), len(folders)))
    for k in sorted(files):
        print("   ", k)
    return 0

if __name__ == "__main__":
    sys.exit(main())
