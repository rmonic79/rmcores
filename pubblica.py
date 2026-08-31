#!/usr/bin/env python3
"""
Pubblica il database rmcores. Fa tutto: commit, push, calcolo del db e ramo db.
Si lancia dal .bat, non serve conoscere git.
"""
import os, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))

def git(*a, check=True):
    r = subprocess.run(["git"] + list(a), cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        print("\n!! git " + " ".join(a) + "\n" + (r.stderr or r.stdout).strip())
        sys.exit(1)
    return (r.stdout or "").strip()

def descrizione_automatica():
    """Ricava la descrizione dagli RBF presenti: nome del core + la sua data.

    La versione non e' scritta da nessuna parte nei file, quindi non si puo'
    indovinare; la data invece sta nel nome dell'RBF, che il post-flow genera
    come <core>_YYYYMMDD[_N].rbf.
    """
    import re
    cores_dir = os.path.join(ROOT, "_Arcade", "cores")
    voci = []
    if os.path.isdir(cores_dir):
        for f in sorted(os.listdir(cores_dir)):
            m = re.match(r"(.+?)_(\d{4})(\d{2})(\d{2})(?:_\d+)?\.rbf$", f)
            if m:
                voci.append("%s %s-%s-%s" % (m.group(1), m.group(2), m.group(3), m.group(4)))
    if voci:
        return ", ".join(voci)
    return time.strftime("aggiornamento %d/%m/%Y")

def main():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        print("!! qui non c'e' un repository git.")
        print("   Aprilo una volta in GitHub Desktop:  File > Add local repository")
        print("   e pubblicalo con  Publish repository.  Poi rilancia questo.")
        return 1

    msg = " ".join(sys.argv[1:]) or descrizione_automatica()

    # 1) i file: commit e push sul ramo principale
    ramo = git("rev-parse", "--abbrev-ref", "HEAD")
    if ramo == "db":
        print("!! sei sul ramo db. Torna sul ramo principale e rilancia."); return 1
    if git("status", "--porcelain"):
        print("Committo i file...")
        git("add", "-A")
        git("commit", "-m", msg)
    else:
        print("Nessun file cambiato, uso l'ultimo commit.")
    print("Mando su GitHub il ramo", ramo, "...")
    git("push", "origin", ramo)
    sha = git("rev-parse", "HEAD")
    print("Commit:", sha)

    # 2) il database, agganciato a QUESTO commit
    print("Calcolo il database...")
    r = subprocess.run([sys.executable, "gen_db.py", sha], cwd=ROOT)
    if r.returncode != 0:
        print("!! generazione del database fallita"); return 1

    # 3) il ramo db: contiene solo db.json.zip
    print("Pubblico il ramo db...")
    git("add", "db.json", "db.json.zip")
    if git("status", "--porcelain", "--", "db.json", "db.json.zip"):
        git("commit", "-m", "db " + msg)
        git("push", "origin", ramo)
    git("branch", "-f", "db", "HEAD")
    git("push", "-f", "origin", "db")
    print("""
Fatto. Gli utenti ricevono l'aggiornamento al prossimo Update All.
Il loro downloader.ini deve avere:

  [rmonic79/rmcores]
  db_url = https://raw.githubusercontent.com/rmonic79/rmcores/db/db.json.zip
""")
    return 0

if __name__ == "__main__":
    sys.exit(main())
