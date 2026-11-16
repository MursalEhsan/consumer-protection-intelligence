"""Prepare a deterministic, strictly date-bounded local archive sample."""
import hashlib
import re
from pathlib import Path

import pandas as pd
import yaml
from datasketch import MinHash, MinHashLSH

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "config/split.yaml").read_text())
TEXT = "Consumer complaint narrative"
ID = "Complaint ID"


def load_split(directory: Path, split: str) -> pd.DataFrame:
    number = dict(zip(("train", "validation", "test"), CFG["archive_exports"]))[split]
    source, = directory.glob(f"CCDB_Export_{number}_*.zip")
    fields = [ID, TEXT, "Date received", "Product", "Issue"]
    start, end = map(str, CFG[split])
    kept = []
    for part in pd.read_csv(source, dtype=str, usecols=fields, chunksize=50000):
        part = part.dropna(subset=fields)
        part = part[part["Date received"].between(start, end) & part[TEXT].str.strip().ne("")]
        part["key"] = part[ID].map(lambda x: hashlib.sha256(f"{CFG['seed']}:{x}".encode()).hexdigest())
        kept.append(part.sort_values("key").head(CFG["sample_caps"][split]))
    return pd.concat(kept).sort_values("key").drop_duplicates(ID).head(CFG["sample_caps"][split])


class DuplicateFilter:
    def __init__(self) -> None:
        self.index = MinHashLSH(threshold=0.8, num_perm=CFG["minhash_permutations"])
        self.words = {}
        self.ids = set()
        self.exact = set()

    def apply(self, frame: pd.DataFrame) -> pd.DataFrame:
        keep = []
        for i, row in frame.reset_index(drop=True).iterrows():
            tokens = re.findall(r"\w+", row[TEXT].casefold())
            normalized = " ".join(tokens)
            if not tokens or row[ID] in self.ids or normalized in self.exact:
                continue
            shingles = {" ".join(tokens[j:j+3]) for j in range(len(tokens)-2)} or {normalized}
            mh = MinHash(num_perm=CFG["minhash_permutations"], seed=CFG["seed"])
            mh.update_batch([s.encode() for s in shingles])
            if any(len(shingles & self.words[k])/len(shingles | self.words[k]) >= CFG["duplicate_jaccard"] for k in self.index.query(mh)):
                continue
            self.ids.add(row[ID])
            self.exact.add(normalized)
            self.words[row["key"]] = shingles
            self.index.insert(row["key"], mh)
            keep.append(i)
        return frame.iloc[keep].reset_index(drop=True)
