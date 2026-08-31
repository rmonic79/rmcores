# rmcores — custom database for the MiSTer Downloader

My cores, installed and kept up to date automatically by **Update All**.

## For users

Add these two lines at the end of `downloader.ini`, in the root of the SD card,
then run Update All:

```ini
[rmonic79/rmcores]
db_url = https://raw.githubusercontent.com/rmonic79/rmcores/db/db.json.zip
```

The MRA files land in `_Arcade/_rmCores/` — a folder of their own, so my
versions are grouped together and never mix with the official ones — and the
cores in `_Arcade/cores/`, where the MiSTer looks for them.

The RBF names are prefixed with `rm`, so they can live next to the official
cores on the same card without overwriting anything.

## For me — how to publish an update

1. Drop the new files in this repository, keeping the paths exactly as they must
   appear on the SD card (`_Arcade/_rmCores/*.mra`, `_Arcade/cores/*.rbf`).
2. Commit and push them to the branch that holds the files.
3. Take that commit's SHA and run:

   ```
   python gen_db.py <commit_sha>
   ```

   It walks `_Arcade/`, computes MD5 and size for every file, and writes
   `db.json` plus `db.json.zip`. The SHA goes into `base_files_url`, so the
   download URLs point at a fixed revision instead of a moving branch.
4. Publish `db.json.zip` on the `db` branch, which is what `db_url` points to.

Notes that matter:

- the hash must be **MD5** — that is what the Downloader checks;
- `db_id` in the JSON must match the section name in `downloader.ini`;
- every RBF gets a `tangle` entry: the files are dated, so if a new one fails to
  download the previous one is kept instead of being removed, and the core does
  not disappear from the card.

Schema reference: `MiSTer-devel/Downloader_MiSTer`, `docs/custom-databases.md`.
