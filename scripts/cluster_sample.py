"""Create an ignored local embedding cache; export no complaint records."""

import argparse
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from fresh_eval import embedding
from fresh_data import TEXT, ID, ROOT


def prepare(directory):
    archives = sorted(directory.glob("CCDB_Export_*.zip"))
    if {int(f.name.split("_")[2]) for f in archives} != set(range(2, 22)):
        raise ValueError("Archive exports 2 through 21 required")
    frames = []
    for f in archives:
        for part in pd.read_csv(
            f, usecols=[ID, TEXT, "Date received", "Product", "Issue"], dtype=str, chunksize=50000
        ):
            part = part.dropna()
            part = part[
                part[ID].map(
                    lambda v: (
                        int.from_bytes(hashlib.sha256(("cluster:" + v).encode()).digest()[:4], "big") % 512
                        == 0
                    )
                )
            ]
            frames.append(part)
    df = pd.concat(frames).sort_values("Date received").drop_duplicates(ID).drop_duplicates(TEXT)
    df = df.drop(columns=ID).reset_index(drop=True)
    folder = ROOT / "output/clusters"
    folder.mkdir(parents=True, exist_ok=True)
    df.to_parquet(folder / "sample.parquet", index=False)
    np.save(folder / "embedding.npy", embedding(df[TEXT]))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    prepare(p.parse_args().directory)
