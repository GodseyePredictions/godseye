import pandas as pd, numpy as np
pd.set_option("display.width",230)
D='/home/user/attd/data/'
sc=pd.read_csv(D+'schedules.csv'); sc=sc[sc.season.between(2021,2026)&(sc.game_type=='REG')&sc.spread_line.notna()&sc.total_line.notna()]
h=sc[['game_id','season','week','home_team','spread_line','total_line']].rename(columns={'home_team':'team'}); h['spr']=h.spread_line
a=sc[['game_id','season','week','away_team','spread_line','total_line']].rename(columns={'away_team':'team'}); a['spr']=-a.spread_line
G=pd.concat([h,a]); G['implied']=G.total_line/2+G.spr/2
W=pd.read_parquet('/home/user/attd/outputs/props_walkforward_2026.parquet')
W=W[W.p.between(0.70,0.88)].copy(); W['d']=(W.p-0.78).abs(); W=W.sort_values('d').drop_duplicates(['game_id','player_id','market']); W['hit']=(W.x>=W.k).astype(int)
W=W.merge(G[['game_id','team','spr','implied']],on=['game_id','team'],how='left')
W['imp']=pd.cut(W.implied,[0,17.5,20,22.5,25,40]).astype(str)
r=W.groupby('imp').agg(n=('hit','size'),priced=('p','mean'),hit=('hit','mean')); r['gap']=r.hit-r.priced; print("MODEL floor legs by implied team total (2026)\n",r.round(3))
# ---- fix 2: changed offence = players with >=25% of team targets over prior 3 team games absent this game
T=[]; L=[]
for y in range(2021,2027):
    sw=pd.read_parquet(D+f'stats_week_{y}.parquet'); sw=sw[sw.season_type=='REG'].copy(); sw['targets']=sw.targets.fillna(0); sw['carries']=sw.carries.fillna(0)
    weeks={t:sorted(g.week.unique()) for t,g in sw.groupby('team')}
    tg=sw.groupby(['team','week','player_id']).agg(t=('targets','sum'),c=('carries','sum'),pos=('position','first'),rec=('receptions','sum'),ryd=('receiving_yards','sum'),ru=('rushing_yards','sum')).reset_index()
    for team,g in tg.groupby('team'):
        ws=weeks[team]
        for i,w in enumerate(ws):
            if i<3: continue
            prev=g[g.week.isin(ws[i-3:i])]; cur=g[g.week==w]
            sh=prev.groupby('player_id').t.sum()/max(prev.t.sum(),1); miss=sh[~sh.index.isin(cur.player_id)]
            csh=prev[prev.pos=='RB'].groupby('player_id').c.sum(); lead=csh.idxmax() if len(csh) and csh.max()>=30 else None
            lead_out=lead is not None and lead not in set(cur.player_id)
            repl=None
            if lead_out:
                rest=csh[csh.index.isin(cur.player_id)]
                repl=rest.idxmax() if len(rest) else None
            T.append((y,w,team,float(miss.sum()),lead_out,repl))
T=pd.DataFrame(T,columns=['season','week','team','miss_share','lead_out','repl'])
print(T.miss_share.describe().round(3).to_dict(), (T.miss_share>=0.25).mean().round(3), T.lead_out.mean().round(3))
# model-free floor legs again (receiving + rushing), keep player ids
RUNG={"receptions":[1,2,3,4,5,6,7,8],"receiving_yards":list(range(20,131,10)),"rushing_yards":list(range(20,131,10)),"carries":[10,15,20,25]}
rows=[]
for y in range(2021,2027):
    sw=pd.read_parquet(D+f'stats_week_{y}.parquet'); sw=sw[sw.season_type=='REG'].sort_values('week')
    for col,rg in RUNG.items():
        s=sw[['player_id','team','week',col]].copy(); s[col]=s[col].fillna(0)
        for pid,q in s.groupby('player_id'):
            vals=q[col].tolist()
            if len(vals)<6: continue
            ws=q.week.tolist(); ts=q.team.tolist()
            for i in range(5,len(vals)):
                prior=np.array(vals[:i]); ok=[k for k in rg if (prior>=k).mean()>=0.75]
                if ok: rows.append((y,ws[i],ts[i],pid,col,max(ok),int(vals[i]>=max(ok))))
B=pd.DataFrame(rows,columns=['season','week','team','player_id','col','k','hit']).merge(T,on=['season','week','team'])
B['changed']=B.miss_share>=0.25
rc=B[B.col.isin(['receptions','receiving_yards'])]
r=rc.groupby('changed').agg(n=('hit','size'),hit=('hit','mean')); print("FIX 2: receiving floor legs, team missing 25%+ of recent targets\n",r.round(3))
rc2=rc.assign(ms=pd.cut(rc.miss_share,[-.01,.05,.15,.25,.40,1]).astype(str)); print(rc2.groupby('ms').agg(n=('hit','size'),hit=('hit','mean')).round(3))
a_,b_=rc[rc.changed].hit,rc[~rc.changed].hit; print("diff",round(a_.mean()-b_.mean(),3),"se",round(np.sqrt(a_.var()/len(a_)+b_.var()/len(b_)),3))
# ---- fix 3: replacement lead back when the lead back is out: his own prior-based floor rushing lines + raw production
ru=B[B.col.isin(['rushing_yards','carries'])]
rp=ru[ru.lead_out&(ru.player_id==ru.repl)]; print("FIX 3: replacement back's floor rushing lines when lead is out: n",len(rp),"hit",round(rp.hit.mean(),3),"| all other backs' floor rushing lines hit",round(ru[~(ru.lead_out&(ru.player_id==ru.repl))].hit.mean(),3))
# raw: replacement back's rushing yards in that game vs his prior average
allr=[]
for y in range(2021,2027):
    sw=pd.read_parquet(D+f'stats_week_{y}.parquet'); sw=sw[sw.season_type=='REG']; x=sw.groupby(['player_id','team','week']).agg(c=('carries','sum'),ry=('rushing_yards','sum')).reset_index(); x['season']=y; allr.append(x)
X=pd.concat(allr).sort_values(['season','player_id','week']); X['c_prior']=X.groupby(['season','player_id']).c.transform(lambda s: s.shift(1).rolling(3,min_periods=1).mean()); X['ry_prior']=X.groupby(['season','player_id']).ry.transform(lambda s: s.shift(1).rolling(3,min_periods=1).mean())
R=T[T.lead_out&T.repl.notna()].merge(X,left_on=['season','week','team','repl'],right_on=['season','week','team','player_id'])
print("replacement backs: n",len(R),"prior carries",round(R.c_prior.mean(),1),"-> actual",round(R.c.mean(),1),"| prior rush yds",round(R.ry_prior.mean(),1),"-> actual",round(R.ry.mean(),1),"| 20+ yds",round((R.ry>=20).mean(),3),"30+",round((R.ry>=30).mean(),3),"40+",round((R.ry>=40).mean(),3),"10+ car",round((R.c>=10).mean(),3))
