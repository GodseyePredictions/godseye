import sys, json; sys.path.insert(0,'/home/user/attd')
import pandas as pd, numpy as np
from itertools import combinations
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer
from attd.window_pdf import B, H2, SUB, T, _tbl
from attd.script_sgp import _joint, _greedy, leg_text, game_script, leg_fit, FIT_WEIGHT
from attd.atd_slip import am, joint, CUSHION
O='outputs/'; F=pd.read_parquet(O+'projection_features_2026_wk11.parquet'); L=pd.read_csv(O+'prop_ladders_2026_wk11.csv'); A=pd.read_csv(O+'atd_2026_wk11.csv')
corr=json.load(open('models/leg_correlations.json')); c2=json.load(open('models/correlations.json')); g='2026_11_CIN_WAS'; prof=game_script(F,g)
cols=["game_id","team","player_id","name","pos_group","market","k","p","season_hits","season_n","fit","fit_why","score"]
def pool(lo,hi,mr):
    q=L[(L.game_id==g)&(L.market!="atd")&L.role_ok&~L.singles_only&(L.season_n.fillna(0)>=4)&L.p.between(lo,hi)&(L.season_rate.fillna(0)>=mr)].copy()
    q=q.sort_values("k",ascending=False).drop_duplicates(["player_id","market"])
    fits=[leg_fit(r,prof) for r in q.itertuples()]; q["fit"]=[f for f,_ in fits]; q["fit_why"]=[w for _,w in fits]
    q["score"]=np.log(q.p/(1-q.p))+FIT_WEIGHT*q.fit
    return q.sort_values("score",ascending=False).reset_index(drop=True)[cols]
def lt(r):
    s=leg_text(r); rec=f" ({int(r.season_hits)} of {int(r.season_n)})" if pd.notna(r.season_n) else ""
    return s, f"{r.p:.0%}{rec}"
story=[Paragraph("God's Eye · Week 11 · Monday night full slate · Bengals @ Commanders",T),
 Paragraph(f"Built {datetime.utcnow():%a %b %-d %H:%M} UTC · FINAL: official inactives applied; Croskey-Merritt active for Washington. Bengals -6, total 54.5. Bet a slip only if bet365 pays better than its fair price.",SUB),Spacer(1,6)]
summ=[["Slip","Legs","Chance","Fair price"]]; log={}
def block(title,d,p,note=""):
    rows=[[f"{title} · {p:.1%} · fair {am(p)}",""]]+[[f"{i+1}. {lt(r)[0]}",lt(r)[1]] for i,r in enumerate(d.itertuples())]
    summ.append([title,str(len(d)),f"{p:.1%}",am(p)]); log[title]={"p":p,"legs":[leg_text(r) for r in d.itertuples()]}
    b=[_tbl(rows,[5.2,1.9])]
    if note: b.append(Paragraph(note,SUB))
    b.append(Spacer(1,5)); return KeepTogether(b)
sec=[]
# 1 safer
q=pool(0.80,0.97,0.75); lad=_greedy(q,corr,10); s1=[Paragraph("1. Props SGPs · safer (lower milestones)",H2)]
for n in (6,8,10):
    d=lad.head(n); s1.append(block(f"Safer {n}-leg",d,_joint(d,corr)))
# 2 higher
q=pool(0.62,0.80,0.55); lad=_greedy(q,corr,10); s2=[Paragraph("2. Props SGPs · higher milestones",H2)]
for n in (6,8,10):
    d=lad.head(n); s2.append(block(f"Higher {n}-leg",d,_joint(d,corr)))
# 3 ATD
W=F[F.game_id==g].drop_duplicates('name'); bd=W[W.p_attd>=.18].sort_values('p_attd',ascending=False)
rows=[["Player","Team","Chance","Fair price","Play at or better","Note"]]
for r in bd.itertuples(): rows.append([r.name,r.team,f"{r.p_attd:.0%}",am(r.p_attd),am(r.p_attd-CUSHION.get(r.pos_group,.05)),"single only" if r.singles_only else ""])
s3=[Paragraph("3. Anytime TD board and slips",H2),_tbl(rows,[2.0,.6,.8,.9,1.3,1.5]),Spacer(1,5)]
ok=bd[~bd.singles_only.astype(bool)].head(7); rows=[["ATD slip","Chance","Fair price"]]
for n,keep in ((2,4),(3,4),(4,2)):
    res=sorted([(joint(ok.iloc[list(ix)],c2),list(ok.iloc[list(ix)].name)) for ix in combinations(range(len(ok)),n)],key=lambda x:-x[0])[:keep]
    for p,nm in res: rows.append([" + ".join(nm),f"{p:.1%}",am(p)]); log["ATD "+" + ".join(nm)]={"p":p,"legs":nm}
s3+=[_tbl(rows,[5.0,1.0,1.1]),Spacer(1,5)]
# 4 SGP + ATDs
a=A[A.game_id==g].copy(); a["market"]="atd"; a["k"]=np.nan; a["season_hits"]=np.nan; a["season_n"]=np.nan; a["fit"]=0; a["fit_why"]=""; a["score"]=0
q=pool(0.70,0.90,0.65); s4=[Paragraph("4. SGPs with anytime TDs (medium risk)",H2)]
for nm,pair in (("1 TD · Chase",["Ja'Marr Chase"]),("2 TDs · Chase + Higgins",["Ja'Marr Chase","Tee Higgins"]),("2 TDs · Chase + Brown",["Ja'Marr Chase","Chase Brown"])):
    s=a[a.name.isin(pair)][cols]
    for n in (6,8):
        d=_greedy(pd.concat([s,q]),corr,n,seed=s,atd_cap=len(pair)); s4.append(block(f"{n}-leg · {nm}",d,_joint(d,corr)))
# 5 market + ATD
C=pd.read_csv(O+'internal/market_test_2026_wk11_MNF_lines_v2.csv')
def leg(n,m,k=None): return a[a.name==n].iloc[[0]] if m=="atd" else L[(L.game_id==g)&(L.name==n)&(L.market==m)&(L.k==k)].iloc[[0]]
U=[("Chig Okonkwo","rec",4.5,"receptions"),("Antonio Williams","rec",3.5,"receptions"),("Jayden Daniels","rush_yds",42.5,"rush yds")]
up=[float(1-C[(C.name==n)&(C.market==m)].p_over.iloc[0]) for n,m,_,_ in U]
s5=[Paragraph("5. TEST · market over/under lines with an anytime TD (lotto)",H2),Paragraph("DraftKings lines compared with the model. A line is used only when the model (60%+), the player's season record (55%+) and the same role against this defence (55%+) all point the same way. Chance is an estimate: the overs are priced together and the unders multiplied in as independent.",SUB),Spacer(1,3)]
base=[("Ja'Marr Chase","atd"),("Joe Burrow","pass_td",1),("Joe Burrow","pass_yds",225),("Ja'Marr Chase","rec",5),("Tee Higgins","rec_yds",30)]
for nm,l in (("Lotto 8-leg",base),("Lotto 10-leg",base+[("Chase Brown","rush_yds",20),("Stefon Diggs","rec",2)])):
    d=pd.concat([leg(*x) for x in l],ignore_index=True); p=_joint(d[[c for c in L.columns if c in d.columns]],corr)*float(np.prod(up))
    rows=[[f"{nm} · about {p:.1%} · fair about {am(p)}",""]]; k=1; d1=d.iloc[:1]
    rows.append([f"1. {leg_text(d.iloc[0])}",f"{d.p.iloc[0]:.0%}"])
    for (n,m,ln,lab),pp in zip(U,up): k+=1; rows.append([f"{k}. {n} UNDER {ln} {lab} (market line)",f"{pp:.0%}"])
    for r in d.iloc[1:].itertuples(): k+=1; rows.append([f"{k}. {lt(r)[0]}",lt(r)[1]])
    summ.append([nm+" (test)",str(k),f"~{p:.1%}",am(p)]); log[nm]={"p":p,"legs":[x[1].split('. ',1)[-1] if False else x[0] for x in rows[1:]]}
    s5.append(KeepTogether([_tbl(rows,[5.2,1.9]),Spacer(1,5)]))
mr=[["Player","Market","Line","Model midpoint","Model side","Season","Role vs defence"]]
for r in C[C.note.fillna("")==""].sort_values("p_side",ascending=False).head(18).itertuples():
    mr.append([r.name,r.market,str(r.line),str(r.model_mid),f"{r.side} {r.p_side:.0%}",f"{r.rec_side:.0%}",f"{r.read_side:.0%}" if pd.notna(r.read_side) else "-"])
s5+=[Paragraph("Market lines against the model (largest gaps)",B),_tbl(mr,[1.7,.8,.6,1.1,1.0,.8,1.1])]
story+=[Paragraph("Summary",H2),_tbl(summ,[3.6,.7,1.0,1.1]),Spacer(1,6)]+s1+s2+s3+s4+s5
out='outputs/Full_Slate_2026_Wk11_MNF_CIN_WAS.pdf'
SimpleDocTemplate(out,pagesize=letter,leftMargin=.6*inch,rightMargin=.6*inch,topMargin=.5*inch,bottomMargin=.5*inch).build(story)
json.dump(log,open('outputs/internal/mnf_wk11_full_slate_slips.json','w'),indent=1,default=str)
for r in summ: print(r)
for k,v in log.items(): print(k,v["legs"])
