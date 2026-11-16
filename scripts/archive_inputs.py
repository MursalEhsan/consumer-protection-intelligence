"""Download the fixed official archive inputs, or verify an existing local copy."""

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config/archive_inputs.json"


def verify(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def download(directory: Path, classification_only: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for row in json.loads(MANIFEST.read_text()):
        if classification_only and row["export"] not in [5, 6, 7]:
            continue
        target = directory / row["name"]
        if target.exists() and verify(target) == row["sha256"]:
            continue
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as f:
            tmp = Path(f.name)
        try:
            urllib.request.urlretrieve(row["url"], tmp)
            if verify(tmp) != row["sha256"]:
                raise ValueError(f"Source revision: {target.name}")
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--classification-only", action="store_true")
    a = p.parse_args()
    download(a.directory, a.classification_only)
