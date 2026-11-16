"""Build a synthetic, stratified text fixture with precomputed MiniLM embeddings."""

import numpy as np
import pandas as pd
from fresh_data import ROOT, TEXT
from fresh_eval import embedding


def main() -> None:
    topics = {
        "billing": ["My demo card bill shows a duplicate charge", "The shop charged my card twice"],
        "transfer": ["My demo transfer has not arrived", "Money I sent is missing from my wallet"],
        "report": ["The demo credit report contains an error", "My credit history lists a wrong balance"],
    }
    rows = []
    for month in pd.period_range("2024-01", periods=3, freq="M"):
        for issue, phrases in topics.items():
            for i in range(6):
                rows.append(
                    (
                        str(month.start_time.date()),
                        "Synthetic account",
                        issue,
                        f"{phrases[i % 2]}. Fictional scenario {month} example {i}.",
                    )
                )
    df = pd.DataFrame(rows, columns=["Date received", "Product", "Issue", TEXT])
    df["embedding"] = list(np.asarray(embedding(df[TEXT]), dtype=np.float32))
    df.rename(columns={TEXT: "synthetic_text"}).to_parquet(
        ROOT / "tests/fixtures/synthetic_embeddings.parquet", index=False
    )


if __name__ == "__main__":
    main()
