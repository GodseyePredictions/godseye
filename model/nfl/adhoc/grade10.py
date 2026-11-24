import re, json, pandas as pd, numpy as np
SP='/tmp/claude-0/-home-user/7a5522a0-8fdf-5649-a562-b33c51387325/scratchpad/'
sw=pd.read_parquet('/home/user/attd/data/stats_week_2026.parquet'); sw=sw[(sw.week==10)&(sw.season_type=="REG")]
nk=lambda s: re.sub(r"(jr|sr|ii|iii|iv)$","",re.sub(r"[^a-z]","",str(s).lower()))
sw["nk"]=sw.player_display_name.map(nk)
tdc=[c for c in sw.columns if c.endswith("_tds") and not c.startswith("passing") and "def" not in c]
sw["atd"]=sw[[c for c in ["rushing_tds","receiving_tds","special_teams_tds"] if c in sw.columns]].fillna(0).sum(axis=1)
S=sw.groupby("nk").agg({**{c:"sum" for c in ["receptions","receiving_yards","rushing_yards","carries","attempts","passing_yards","passing_tds","atd"]},"team":"last"})
MK={"receptions":"receptions","rec yds":"receiving_yards","rush yds":"rushing_yards","carries":"carries","pass att":"attempts","pass yds":"passing_yards","pass TDs":"passing_tds"}
def grade(name,mk,k):
    r=S.loc[nk(name)] if nk(name) in S.index else None
    if r is None: return (None,False)
    if mk=="atd": return (int(r.atd), r.atd>0)
    v=r[MK[mk]]; return (int(v), v>=k)
leg_re=re.compile(r"^(\d+)\. (.+?) (\d+)\+ (receptions|rec yds|rush yds|carries|pass att|pass yds|pass TDs)\b.*?\(?(\d+)%\)?$")
atd_re=re.compile(r"^(\d+)\. (.+?) ANYTIME TD .*?(\d+)%$")
atdt_re=re.compile(r"^(\d+)\. (.+?) (RB|QB|WR|TE) ([A-Z]{2,3}) [A-Z]{2,3} @ [A-Z]{2,3} (\d+)%$")
game_re=re.compile(r"^([A-Z]{2,3} @ [A-Z]{2,3})( \d+\.\d% · [+-]\d+)?$")
def parse(fn,slate):
    T=[]; cur=None; sec=None; game=None
    for ln in open(SP+fn).read().split("\n"):
        ln=ln.strip()
        m=re.match(r"^(\d+)-LEG ATD · ([\d.]+)%",ln)
        if m: cur={"slate":slate,"kind":"ATD ticket","name":f"{m.group(1)}-leg ATD","p":float(m.group(2))/100,"legs":[]}; T.append(cur); sec="atd"; continue
        m=re.match(r"^Master (\d+)-leg per game · (\d+) legs · ([\d.]+)%",ln)
        if m: sec="master"; mn=int(m.group(1)); cur=None; continue
        if ln.startswith("3. ") and "SGPs per game" in ln: sec="hyb"; cur=None; continue
        m=re.match(r"^Slip (A|B) · (\d) ATD \+ (\d+) props · ([\d.]+)%",ln)
        if m and sec=="hyb": cur={"slate":slate,"kind":f"Hybrid {m.group(2)} ATD","name":f"{game} · {m.group(2)} ATD + {m.group(3)} props","game":game,"p":float(m.group(4))/100,"legs":[]}; T.append(cur); continue
        g=game_re.match(ln)
        if g:
            game=g.group(1)
            if sec=="master" and cur is not None and g.group(2): cur["game"]=game; cur["name"]=f"{game} · {mn}-leg props"; cur["p"]=float(g.group(2).split("%")[0])/100
            continue
        if sec=="atd":
            m=atdt_re.match(ln)
            if m and cur: cur["legs"].append({"name":m.group(2),"mk":"atd","k":None,"p":int(m.group(5))/100})
            continue
        m=atd_re.match(ln)
        if m and cur is not None and sec=="hyb": cur["legs"].append({"name":m.group(2),"mk":"atd","k":None,"p":int(m.group(3))/100}); continue
        m=leg_re.match(ln)
        if m:
            if sec=="master" and m.group(1)=="1": cur={"slate":slate,"kind":f"Props {mn}-leg","name":"?","p":None,"legs":[]}; T.append(cur)
            if cur is not None: cur["legs"].append({"name":m.group(2),"mk":m.group(4),"k":int(m.group(3)),"p":int(m.group(5))/100})
    return T
T=parse("Early_Slate_Slips_2026_Wk10.txt","Early")+parse("Afternoon_Evening_Slips_2026_Wk10.txt","Afternoon+Evening")
# mixed tickets and pass-catcher singles as shipped (from the build logs)
mixE=["James Cook","Chris Olave","Bijan Robinson","Tetairoa McMillan","Tony Pollard","Parker Washington","Woody Marks","Matthew Golden","Jonathan Taylor","Xavier Worthy"]
pE=[.66,.45,.58,.41,.50,.40,.44,.39,.43,.37]
for n,pp in ((4,.07259),(6,.01464),(8,.00253),(10,.00041)):
    T.append({"slate":"Early","kind":"ATD mixed","name":f"{n}-leg mixed ATD","p":pp,"legs":[{"name":a,"mk":"atd","k":None,"p":b} for a,b in zip(mixE[:n],pE[:n])]})
T.append({"slate":"Afternoon+Evening","kind":"ATD mixed","name":"4-leg mixed ATD","p":.09218,"legs":[{"name":a,"mk":"atd","k":None,"p":b} for a,b in zip(["Christian McCaffrey","Ja'Marr Chase","Javonte Williams","DK Metcalf"],[.71,.51,.67,.37])]})
singles=[("Early","Chris Olave",.45),("Early","Tetairoa McMillan",.41),("Early","Parker Washington",.40),("Early","Matthew Golden",.39),("Early","Drake London",.37),("Early","Xavier Worthy",.37),("Early","Travis Kelce",.35),("Early","Rashee Rice",.34),("Early","Nico Collins",.34),("Early","Tyler Warren",.34),
 ("Afternoon+Evening","George Kittle",.53),("Afternoon+Evening","Ja'Marr Chase",.51),("Afternoon+Evening","CeeDee Lamb",.49),("Afternoon+Evening","Tee Higgins",.44),("Afternoon+Evening","Ryan Flournoy",.41),("Afternoon+Evening","DK Metcalf",.37),("Afternoon+Evening","Jordan Watkins",.30),("Afternoon+Evening","Germie Bernard",.27)]
for t in T:
    for l in t["legs"]:
        v,h=grade(l["name"],l["mk"],l["k"]); l["val"]=v; l["hit"]=bool(h)
    t["hits"]=sum(l["hit"] for l in t["legs"]); t["n"]=len(t["legs"]); t["cashed"]=t["hits"]==t["n"] and t["n"]>0
SG=[{"slate":s,"name":n,"p":p,"val":grade(n,"atd",None)[0],"hit":bool(grade(n,"atd",None)[1])} for s,n,p in singles]
json.dump({"tickets":T,"singles":SG},open("/home/user/attd/outputs/internal/graded_2026_wk10_sunday.json","w"),indent=1)
for t in T: print(f'{t["slate"][:5]:5} {t["kind"]:13} {t["name"]:34} p={t["p"] if t["p"] is None else round(t["p"],4)} {t["hits"]}/{t["n"]} {"CASHED" if t["cashed"] else ""}  miss: '+", ".join(f'{l["name"]} {l["k"] or ""}{"+" if l["k"] else ""}{l["mk"]}({l["val"]})' for l in t["legs"] if not l["hit"]))
legs={}
for t in T:
    for l in t["legs"]: legs[(l["name"],l["mk"],l["k"])]=l
L=pd.DataFrame(legs.values()); L["type"]=np.where(L.mk=="atd","ATD","prop")
print(L.groupby("type").agg(n=("hit","size"),hit=("hit","mean"),exp=("p","mean")).round(3))
print(L[L.type=="prop"].groupby("mk").agg(n=("hit","size"),hit=("hit","mean"),exp=("p","mean")).round(3))
print("ATD unique legs:"); print(L[L.type=="ATD"][["name","p","val","hit"]].to_string(index=False))
print("singles:",[(s["name"],s["p"],s["hit"]) for s in SG], sum(s["hit"] for s in SG), sum(s["p"] for s in SG))
print("none-matched:", L[L.val.isna()].name.tolist())
