"""Export the fitted SVC without any raw strings from its learned vocabulary."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
from fresh_data import ROOT


def export(path: Path) -> None:
    freeze=json.loads((ROOT/"reports/frozen_choices.json").read_text())
    name=freeze["best"]
    if name!="tfidf_svc":
        raise ValueError("Exporter only supports the frozen linear SVC")
    frozen=ROOT/"output/fresh/frozen.joblib"
    if hashlib.sha256(frozen.read_bytes()).hexdigest()!=freeze["model_sha256"]:
        raise ValueError("Unexpected input checksum")
    models,_=joblib.load(frozen)
    vec,svc=models[name].steps[0][1],models[name].steps[1][1]
    digests=[hashlib.sha256(word.encode()).hexdigest() for word in vec.get_feature_names_out()]
    np.savez_compressed(path,vocabulary_sha256=np.array(digests,dtype="S64"),idf=vec.idf_,weights=svc.coef_,
        intercept=svc.intercept_,classes=freeze["classes"],temperature=freeze["settings"][name]["temperature"],
        threshold=freeze["settings"][name]["threshold"])


if __name__=="__main__":
    export(ROOT/"output/fresh/complaint-svc.npz")
