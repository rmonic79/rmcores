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
