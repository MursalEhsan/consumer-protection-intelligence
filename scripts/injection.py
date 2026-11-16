"""Inject sustained two-month spikes into historical product series."""
import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests
from backtest import legacy_source
from cfpb_pipeline import screen_issue_month
from detector import CFG, ROOT, aggregate, forecast, tail


def main():
    out=ROOT/"reports"
    raw=pd.read_parquet(out/"product_monthly.parquet")
    a=aggregate(raw)
    scored=pd.read_parquet(out/"detector_replay.parquet")
    overall=legacy_source(raw)
    candidates=scored[scored["count"].gt(0)].copy()
    candidates["volume"]=pd.qcut(candidates.expected,3,labels=["low","medium","high"])
    trials=[]
    for volume,g in candidates.groupby("volume",observed=True):
        for r in g.sample(frac=1,random_state=CFG["seed"]).itertuples():
            one=pd.Period(r.month,"M")
            months=[str(one),str(one+1)]
            panel=scored[(scored["product"]==r.product)&(scored.issue==r.issue)].set_index("month")
            if not all(m in panel.index and panel.loc[m,"count"]>0 for m in months):continue
            history=a[(a.Product==r.product)&(a.issue_key==r.issue)].set_index("month").issue_count
            # Only raw identity-mapped cases enter the legacy comparison.
            if not all(((overall.issue==r.issue)&(overall.complaint_month==m)).any() for m in months):continue
            for factor in CFG["spikes"]:
                adjusted=history.copy(); obs=overall.copy();passed=[]
                hits={"legacy":False,"rolling_z":False,"ewma":False,"glm":False}
                for m in months:
                    t=pd.Period(m,"M")
                    h=adjusted.reindex(pd.period_range(t-CFG["window"],t-1,freq="M").astype(str),fill_value=0)
                    y=int(np.ceil(history[m]*factor));extra=y-history[m]
                    mu,alpha=forecast(h.to_numpy())
                    pool=scored[scored.month==m].copy()
                    pos=(pool["product"]==r.product)&(pool.issue==r.issue)
                    pool.loc[pos,"p"]=tail(y,mu,alpha)
                    passed.append(bool(multipletests(pool.p,method="fdr_bh")[1][pos][0]<CFG["family_alpha"]))
                    hits["rolling_z"] |= y>h.mean()+CFG["z"]*h.std()
                    hits["ewma"] |= y>h.ewm(alpha=CFG["ewma_alpha"],adjust=False).mean().iloc[-1]+CFG["z"]*h.std()
                    mask=obs.complaint_month==m
                    obs.loc[mask,"monthly_denominator"]+=extra
                    obs.loc[mask & obs.issue.eq(r.issue),"complaint_count"]+=extra
                    obs.loc[mask,"complaint_share"]=obs.loc[mask,"complaint_count"]/obs.loc[mask,"monthly_denominator"]
                    flagged,_=screen_issue_month(obs[obs.issue==r.issue],m)
                    hits["legacy"] |= not flagged.empty
                    adjusted.loc[m]=y
                hits["glm"]=all(passed)
                for method,hit in hits.items():
                    trials.append((volume,r.month,r.product,r.issue,factor,method,bool(hit)))
            if sum(i[0]==volume for i in trials)>=12*len(CFG["spikes"])*4:break
    trials=pd.DataFrame(trials,columns=["volume","month","product","issue","factor","method","detected"])
    trials.groupby(["volume","factor","method"]).detected.agg(["size","sum","mean"]).rename(columns={"mean":"power"}).to_csv(out/"spike_power.csv")


if __name__=="__main__":
    main()
