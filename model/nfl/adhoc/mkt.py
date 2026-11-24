import json, urllib.request, re, sys
import pandas as pd, numpy as np
sys.path.insert(0,'/home/user/attd')
S='/tmp/claude-0/-home-user/7a5522a0-8fdf-5649-a562-b33c51387325/scratchpad/'
def get(u): return json.loads(urllib.request.urlopen(urllib.request.Request(u.replace("http://","https://"),headers={"User-Agent":"Mozilla/5.0"}),timeout=30).read())
it=json.load(open(S+'props_raw.json'))
MK={'Total Receiving Yards (incl. overtime)':'rec_yds','Total Receptions (incl. overtime)':'rec','Total Rushing Yards (incl. overtime)':'rush_yds','Total Carries (incl. overtime)':'carries','Total Passing Yards (incl. overtime)':'pass_yds','Total Passing Attempts (incl. overtime)':'pass_att','Total Passing Touchdowns (incl. overtime)':'pass_td'}
rows={}
for i in it:
    m=MK.get(i["type"]["name"])
    if not m or "athlete" not in i or not i.get("current",{}).get("target"): continue
    aid=re.search(r"athletes/(\d+)",i["athlete"]["$ref"]).group(1)
    rows[(aid,m)]=(i["current"]["target"]["value"],i.get("open",{}).get("target",{}).get("value"),i["lastUpdated"])
names={}
for aid in {a for a,_ in rows}:
    try:
        a=get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/athletes/{aid}"); names[aid]=(a["displayName"],a.get("position",{}).get("abbreviation"))
    except Exception as e: names[aid]=(aid,"?")
M=pd.DataFrame([(names[a][0],names[a][1],m,v[0],v[1],v[2]) for (a,m),v in rows.items()],columns=["name","pos","market","line","open","upd"])
M.to_csv(S+'market_lines.csv',index=False); print(len(M)); print(M.sort_values(["name","market"]).to_string(index=False))
