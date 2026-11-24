import pandas as pd, numpy as np
pd.set_option("display.width",230)
D='/home/user/attd/data/'
sc=pd.read_csv(D+'schedules.csv'); sc=sc[sc.season.between(2021,2026)&(sc.game_type=='REG')&sc.spread_line.notna()&sc.total_line.notna()]
h=sc[['game_id','season','week','home_team','spread_line','total_line']].rename(columns={'home_team':'team'}); h['spr']=h.spread_line
a=sc[['game_id','season','week','away_team','spread_line','total_line']].rename(columns={'away_team':'team'}); a['spr']=-a.spread_line
G=pd.concat([h,a]); G['implied']=G.total_line/2+G.spr/2
def bucket(r):
    if r.spr<=-10: return '1 dog 10+'
    if r.spr<=-6.5: return '2 dog 6.5-9.5'
    if r.spr<=-3: return '3 dog 3-6'
    if r.spr<3: return '4 close'
    if r.spr<10: return '5 fav 3-9.5'
    return '6 fav 10+'
G['b']=G.apply(bucket,axis=1); G['heavy']=(G.spr<=-10)&(G.implied<17.5)
VOLQ={"pass_att"}; 
# ---------- A. model-based, 2026 walk-forward ----------
W=pd.read_parquet('/home/user/attd/outputs/props_walkforward_2026.parquet')
W=W[W.p.between(0.70,0.88)].copy(); W['d']=(W.p-0.78).abs()
W=W.sort_values('d').drop_duplicates(['game_id','player_id','market']); W['hit']=(W.x>=W.k).astype(int)
W=W.merge(G[['game_id','team','spr','implied','b','heavy']],on=['game_id','team'],how='left')
W['kind']=np.where(W.market=='pass_att','QB attempts',np.where(W.market.isin(['carries','rush_yds']),'rushing',np.where(W.market=='pass_yds','pass yds','receiving')))
print("A. MODEL FLOOR LEGS (70-88%), 2026 walk-forward, n=",len(W))
r=W.groupby('b').agg(n=('hit','size'),priced=('p','mean'),hit=('hit','mean')); r['gap']=r.hit-r.priced; print(r.round(3))
r=W.groupby(['heavy','kind']).agg(n=('hit','size'),priced=('p','mean'),hit=('hit','mean')); r['gap']=r.hit-r.priced; print(r.round(3))
r=W[W.spr<=-10].groupby('kind').agg(n=('hit','size'),priced=('p','mean'),hit=('hit','mean')); r['gap']=r.hit-r.priced; print("dog 10+ by kind\n",r.round(3))
# ---------- B. model-free, 2021-2026 ----------
RUNG={"receptions":[1,2,3,4,5,6,7,8],"receiving_yards":list(range(20,131,10)),"rushing_yards":list(range(20,131,10)),"carries":[10,15,20,25],"attempts":list(range(20,46,5)),"passing_yards":list(range(150,351,25)),"passing_tds":[1,2,3]}
rows=[]
for y in range(2021,2027):
    sw=pd.read_parquet(D+f'stats_week_{y}.parquet'); sw=sw[sw.season_type=='REG'].sort_values('week')
    for col,rg in RUNG.items():
        s=sw[['player_id','team','week','position',col]].copy(); s[col]=s[col].fillna(0)
        if col in('attempts','passing_yards','passing_tds'): s=s[(s.position=='QB')]
        v=s.groupby('player_id')[col].apply(list); wk=s.groupby('player_id').week.apply(list); tm=s.groupby('player_id').team.apply(list)
        for pid,vals in v.items():
            if len(vals)<6: continue
            ws=wk[pid]; ts=tm[pid]
            for i in range(5,len(vals)):
                prior=np.array(vals[:i])
                if col in('attempts','passing_yards','passing_tds') and prior.mean()<(15 if col=='attempts' else 0): continue
                # floor line: hardest rung cleared in >=75% of prior games
                ok=[k for k in rg if (prior>=k).mean()>=0.75]
                if not ok: continue
                k=max(ok); rows.append((y,ws[i],ts[i],col,k,(prior>=k).mean(),int(vals[i]>=k),len(prior)))
B=pd.DataFrame(rows,columns=['season','week','team','col','k','prior_rate','hit','n_prior'])
B=B.merge(G[['season','week','team','spr','implied','b','heavy']],on=['season','week','team'],how='inner')
B['kind']=B.col.map({"attempts":"QB attempts","passing_yards":"pass yds","passing_tds":"pass TDs","carries":"rushing","rushing_yards":"rushing","receptions":"receiving","receiving_yards":"receiving"})
print("\nB. MODEL-FREE FLOOR LINES (cleared 75%+ of prior games), 2021-2026, n=",len(B))
r=B.groupby('b').agg(n=('hit','size'),prior=('prior_rate','mean'),hit=('hit','mean')); print(r.round(3))
r=B.pivot_table(index='kind',columns='b',values='hit',aggfunc='mean'); print(r.round(3)); print(B.pivot_table(index='kind',columns='b',values='hit',aggfunc='size'))
hv=B.groupby(['heavy','kind']).agg(n=('hit','size'),hit=('hit','mean')).unstack(0); print(hv.round(3))
# by implied total
B['imp']=pd.cut(B.implied,[0,15,17.5,20,22.5,25,40]); print(B.groupby('imp',observed=True).agg(n=('hit','size'),hit=('hit','mean')).round(3))
print(B[B.kind!='QB attempts'].groupby('imp',observed=True).agg(n=('hit','size'),hit=('hit','mean')).round(3))
# standard errors heavy vs rest, production legs
for kind in ['receiving','rushing','pass yds','pass TDs','QB attempts']:
    q=B[B.kind==kind]; a=q[q.heavy].hit; b_=q[~q.heavy].hit
    se=np.sqrt(a.var()/max(len(a),1)+b_.var()/len(b_)); print(kind,"heavy",round(a.mean(),3),len(a),"rest",round(b_.mean(),3),len(b_),"diff",round(a.mean()-b_.mean(),3),"se",round(se,3))
# simple ticket simulation: per team-game take up to N random floor legs; heavy-dog legs share one script
B.to_parquet('/tmp/claude-0/-home-user/7a5522a0-8fdf-5649-a562-b33c51387325/scratchpad/dog_bt.parquet')
