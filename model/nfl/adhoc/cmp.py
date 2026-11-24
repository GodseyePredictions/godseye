import json, urllib.request, re, sys
import pandas as pd, numpy as np
sys.path.insert(0,'/home/user/attd')
S='/tmp/claude-0/-home-user/7a5522a0-8fdf-5649-a562-b33c51387325/scratchpad/'
def get(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read())
e=get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401873078"); print(e["header"]["competitions"][0]["status"]["type"]["shortDetail"], e["header"]["competitions"][0]["status"]["type"]["state"])
M=pd.read_csv(S+'market_lines.csv'); L=pd.read_csv('outputs/prop_ladders_2026_wk11.csv'); L=L[L.game_id=='2026_11_CIN_WAS']
nk=lambda s: re.sub(r"(jr|sr|ii|iii|iv)$","",re.sub(r"[^a-z]","",str(s).lower())); L["nk"]=L.name.map(nk)
sw=pd.read_parquet('data/stats_week_2026.parquet'); sw=sw[sw.season_type=='REG'].copy(); sw["nk"]=sw.player_display_name.map(nk)
COL={'rec_yds':'receiving_yards','rec':'receptions','rush_yds':'rushing_yards','carries':'carries','pass_yds':'passing_yards','pass_att':'attempts','pass_td':'passing_tds'}
lg=lambda p:np.log(np.clip(p,1e-4,1-1e-4)/(1-np.clip(p,1e-4,1-1e-4))); sg=lambda z:1/(1+np.exp(-z))
out=[]
for r in M.itertuples():
    l=L[(L.nk==nk(r.name))&(L.market==r.market)].sort_values("k"); need=np.floor(r.line)+1
    g=sw[sw.nk==nk(r.name)]; v=g[COL[r.market]].fillna(0) if len(g) else pd.Series(dtype=float)
    if r.market in('pass_yds','pass_att','pass_td'): v=v[g.attempts.fillna(0)>=10]
    rec=dict(name=r.name,pos=r.pos,market=r.market,line=r.line,open=r.open,n=len(v),over=int((v>r.line).sum()),avg=round(float(v.mean()),1) if len(v) else np.nan,last3=[int(x) for x in v.tail(3)])
    if len(l)>=2:
        ks=l.k.values; ps=l.p.values
        if need<=ks.min(): p=ps[0]; note="below ladder"
        elif need>ks.max(): p=None; note="above ladder"
        else: p=float(sg(np.interp(need,ks,lg(ps)))); note=""
        # model median: k where p crosses .5
        med=float(np.interp(0,-lg(ps),ks)) if (ps.max()>.5>ps.min()) else (ks.max() if ps.min()>.5 else ks.min())
        rec.update(p_over=p,model_mid=round(med,1),note=note,role_ok=bool(l.role_ok.iloc[0]),singles=bool(l.singles_only.iloc[0]),top_k=ks.max(),p_top=round(ps[-1],2))
    else: rec.update(p_over=None,model_mid=None,note="not in model",role_ok=False,singles=False)
    out.append(rec)
C=pd.DataFrame(out); C.to_csv(S+'market_cmp.csv',index=False)
pd.set_option("display.width",250)
print(C[['name','pos','market','line','open','model_mid','p_over','n','over','avg','last3','role_ok','singles','note']].round(2).sort_values(['pos','name','market']).to_string(index=False))
