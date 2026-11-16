"""Freeze validation choices first, then score the reserved period in one pass."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize_scalar
from scipy.special import softmax
from scipy.stats import binomtest
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC
from fresh_data import CFG, ID, ROOT, TEXT, DuplicateFilter, load_split

OUT = ROOT / "reports"
LOCAL = ROOT / "output/fresh"
MAP = yaml.safe_load((ROOT / "config/label_map.yaml").read_text())
CLASSES = sorted(set(MAP["labels"].values()))
SEED = CFG["seed"]


def targets(frame):
    return frame.Issue.map(MAP["labels"]).fillna(MAP["unseen"]).map(CLASSES.index).to_numpy()


def embedding(text):
    from sentence_transformers import SentenceTransformer
    encoder = SentenceTransformer(os.environ.get("CFPB_ENCODER", CFG["encoder"]), revision=CFG["encoder_revision"], device="cpu")
    return encoder.encode(text.tolist(), batch_size=32, normalize_embeddings=True, show_progress_bar=False)


def logits(model, x):
    return model.decision_function(x)


def measures(cm):
    n = cm.sum(1)
    p = cm.sum(0)
    tp = cm.diagonal()
    other = CLASSES.index("Other")
    safe = lambda a,b: np.divide(a,b,out=np.zeros_like(a,dtype=float),where=b!=0)
    f1 = safe(2*tp,n+p)
    return {"accuracy":tp.sum()/n.sum(),"macro_f1":f1.mean(),"weighted_f1":np.average(f1,weights=n),
            "named_accuracy":(tp.sum()-tp[other])/(n.sum()-n[other]),"other_accuracy":tp[other]/n[other],
            "precision":safe(tp,p).tolist(),"recall":safe(tp,n).tolist()}


def fit(directory):
    LOCAL.mkdir(parents=True,exist_ok=True)
    filt=DuplicateFilter()
    tr=filt.apply(load_split(directory,"train"))
    va=filt.apply(load_split(directory,"validation"))
    models={}
    validation={}
    for name in ["majority","stratified","tfidf_logistic","tfidf_svc","minilm_logistic"]:
        x,v=tr[TEXT],va[TEXT]
        if name in ("majority","stratified"):
            model=DummyClassifier(strategy="most_frequent" if name=="majority" else "stratified",random_state=SEED)
        elif name.startswith("tfidf"):
            clf=LinearSVC(random_state=SEED) if name.endswith("svc") else LogisticRegression(max_iter=500,random_state=SEED)
            model=make_pipeline(TfidfVectorizer(ngram_range=(1,2),min_df=2,sublinear_tf=True),clf)
        else:
            x,v=embedding(x),embedding(v)
            model=LogisticRegression(max_iter=500,random_state=SEED)
        model.fit(x,targets(tr))
        pred=model.predict(v)
        score=measures(confusion_matrix(targets(va),pred,labels=range(len(CLASSES))))["macro_f1"]
        t,threshold=1.,1.01
        if name not in ("majority","stratified"):
            s=logits(model,v)
            y=targets(va)
            k=len(y)//2
            temp=minimize_scalar(lambda t:-np.log(softmax(s[:k]/t,axis=1)[np.arange(k),y[:k]].clip(1e-12)).mean(),bounds=(0.1,10),method="bounded")
            t=float(temp.x)
            prob=softmax(s[k:]/t,axis=1)
            for cut in CFG["thresholds"]:
                mask=prob.max(1)>=cut
                if mask.any() and np.mean(pred[k:][mask]==y[k:][mask])>=CFG["validation_min_precision"]:
                    threshold=cut
                    break
        models[name]=model
        validation[name]={"validation_macro_f1":score,"temperature":t,"threshold":threshold}
    best=max(list(models)[2:],key=lambda n:validation[n]["validation_macro_f1"])
    baseline=max(list(models)[:2],key=lambda n:validation[n]["validation_macro_f1"])
    joblib.dump((models,filt),LOCAL/"frozen.joblib")
    freeze={"best":best,"baseline":baseline,"settings":validation,"classes":CLASSES,
            "model_sha256":hashlib.sha256((LOCAL/"frozen.joblib").read_bytes()).hexdigest()}
    (OUT/"frozen_choices.json").write_text(json.dumps(freeze,indent=2)+"\n")


def evaluate(directory):
    freeze=json.loads((OUT/"frozen_choices.json").read_text())
    if hashlib.sha256((LOCAL/"frozen.joblib").read_bytes()).hexdigest()!=freeze["model_sha256"]:
        raise ValueError("Frozen bundle changed")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
    if subprocess.run(["git","diff","--quiet","HEAD","--","scripts","config","reports/frozen_choices.json"]).returncode:
        raise ValueError("Commit protocol and choices before scoring")
    models,filt=joblib.load(LOCAL/"frozen.joblib")
    with (LOCAL/"test_started").open("x") as f:
        f.write(commit)
    test=filt.apply(load_split(directory,"test"))
    y=targets(test)
    predictions={}
    result={"commit":commit,"classes":CLASSES,"rows":len(y),"test_ids_sha256":hashlib.sha256("\n".join(sorted(test[ID])).encode()).hexdigest(),"models":{}}
    result["test_majority_oracle_accuracy"]=float(np.bincount(y).max()/len(y))
    for name,model in models.items():
        x=embedding(test[TEXT]) if name=="minilm_logistic" else test[TEXT]
        pred=model.predict(x)
        predictions[name]=pred
        cm=confusion_matrix(y,pred,labels=range(len(CLASSES)))
        stats=measures(cm)
        rng=np.random.default_rng(SEED)
        draws=rng.multinomial(len(y),cm.ravel()/len(y),size=CFG["bootstrap_resamples"]).reshape(-1,*cm.shape)
        reps=[measures(d) for d in draws]
        stats["bootstrap_95"]={k:np.quantile([r[k] for r in reps],[.025,.975],axis=0).tolist() for k in stats}
        result["models"][name]=stats
        if name==freeze["best"]:
            prob=softmax(logits(model,x)/freeze["settings"][name]["temperature"],axis=1)
            confidence=prob.max(1)
            correct=pred==y
            bins=np.minimum((confidence*CFG["calibration_bins"]).astype(int),CFG["calibration_bins"]-1)
            rel=[(float(confidence[bins==i].mean()),float(correct[bins==i].mean()),int((bins==i).sum())) for i in np.unique(bins)]
            stats["ece"]=sum(abs(a-b)*n for a,b,n in rel)/len(y)
            accepted=confidence>=freeze["settings"][name]["threshold"]
            stats["coverage"]=float(accepted.mean())
            stats["accepted_accuracy"]=float(correct[accepted].mean()) if accepted.any() else None
            plt.figure();plt.plot([0,1],[0,1],"--");plt.plot(*zip(*[(a,b) for a,b,n in rel]),"o-");plt.xlabel("Mean calibrated confidence");plt.ylabel("Observed accuracy");plt.tight_layout();plt.savefig(OUT/"reliability.png");plt.close()
            order=np.argsort(-confidence)
            k=np.arange(1,len(y)+1)
            plt.figure();plt.plot(k/len(y),np.cumsum(correct[order])/k);plt.xlabel("Fraction accepted");plt.ylabel("Accepted accuracy");plt.tight_layout();plt.savefig(OUT/"coverage_accuracy.png");plt.close()
            fig,ax=plt.subplots(figsize=(10,8));img=ax.imshow(cm);ax.set_xticks(range(len(CLASSES)),CLASSES,rotation=90,fontsize=7);ax.set_yticks(range(len(CLASSES)),CLASSES,fontsize=7);ax.set(xlabel="Predicted issue",ylabel="Recorded issue");fig.colorbar(img,label="Narratives");fig.tight_layout();fig.savefig(OUT/"confusion_matrix.png");plt.close(fig)
    a=predictions[freeze["best"]]==y
    b=predictions[freeze["baseline"]]==y
    wins=int((a&~b).sum());loss=int((b&~a).sum())
    result["mcnemar"]={"best":freeze["best"],"validation_selected_baseline":freeze["baseline"],"wins":wins,"losses":loss,"p":binomtest(wins,wins+loss).pvalue if wins+loss else 1.}
    (OUT/"metrics.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    text=["# Fresh historical evaluation","",f"Frozen model: {freeze['best']}. Accuracy difference from retrospective test-majority oracle: {100*(result['models'][freeze['best']]['accuracy']-result['test_majority_oracle_accuracy']):.2f} percentage points.","","| Model | Accuracy | Macro F1 | Named accuracy | Other accuracy |","|---|---:|---:|---:|---:|"]
    for name,s in result["models"].items():
        text.append(f"| {name} | {s['accuracy']:.4f} | {s['macro_f1']:.4f} | {s['named_accuracy']:.4f} | {s['other_accuracy']:.4f} |")
    text.extend(["","[Full metrics, paired test, bootstrap intervals, class order, test hash and run commit](metrics.json). Row-level bootstrap assumes independence after approximate deduplication. This earlier retrospective period does not establish current performance."])
    (OUT/"classifier_eval.md").write_text("\n".join(text)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("phase",choices=["fit","evaluate"])
    p.add_argument("archives",type=Path)
    args=p.parse_args()
    (fit if args.phase=="fit" else evaluate)(args.archives)
