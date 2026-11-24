import sys; sys.path.insert(0,'/tmp/claude-0/-home-user/7a5522a0-8fdf-5649-a562-b33c51387325/scratchpad')
import pandas as pd, numpy as np
from defpos import load
R=[]
for y in (2023,2024,2025,2026):
    p=load(y)
    tg=p[(p.pass_attempt==1)&(p.sack!=1)&p.rpos.isin(['WR','TE','RB','FB'])].copy(); tg['rpos']=tg.rpos.replace({'FB':'RB'})
    tg['cy']=np.where(tg.complete_pass==1,tg.yards_gained,0); tg['cyac']=np.where(tg.complete_pass==1,tg.yards_after_catch.fillna(0),0)
    tg['ctd']=((tg.touchdown==1)&(tg.complete_pass==1)&(tg.td_team==tg.posteam)).astype(int)
    g=tg.groupby(['season','week','defteam','posteam','rpos']).agg(tgt=('pass_attempt','size'),rec=('complete_pass','sum'),yds=('cy','sum'),yac=('cyac','sum'),td=('ctd','sum')).reset_index()
    ru=p[(p.rush_attempt==1)&p.upos.isin(['RB','FB'])].copy(); ru['rtd']=((ru.touchdown==1)&(ru.td_team==ru.posteam)).astype(int)
    h=ru.groupby(['season','week','defteam','posteam']).agg(tgt=('rush_attempt','size'),yds=('yards_gained','sum'),td=('rtd','sum')).reset_index(); h['rpos']='RUSH'; h['rec']=h.tgt; h['yac']=0
    # all team-games so zero rows exist
    games=p.groupby(['season','week','defteam','posteam']).size().reset_index()[['season','week','defteam','posteam']]
    for pos,src in [('WR',g),('TE',g),('RB',g),('RUSH',h)]:
        x=games.merge(src[src.rpos==pos],on=['season','week','defteam','posteam'],how='left').fillna({'tgt':0,'rec':0,'yds':0,'yac':0,'td':0}); x['rpos']=pos; R.append(x)
A=pd.concat(R).sort_values(['season','rpos','defteam','week'])
A['ypt']=A.yds/A.tgt.replace(0,np.nan)
out=[]
for m in ['yds','rec','tgt','yac','td','ypt']:
    # defence season-to-date before this game
    A['d_'+m]=A.groupby(['season','rpos','defteam'])[m].transform(lambda s: s.shift(1).expanding(4).mean())
    # offence season-to-date before this game (same position group)
    A=A.sort_values(['season','rpos','posteam','week']); A['o_'+m]=A.groupby(['season','rpos','posteam'])[m].transform(lambda s: s.shift(1).expanding(4).mean()); A=A.sort_values(['season','rpos','defteam','week'])
for pos in ['WR','TE','RB','RUSH']:
    q=A[(A.rpos==pos)].dropna(subset=['d_yds','o_yds'])
    row={'pos':pos,'n':len(q)}
    for m in ['yds','rec','td','yac','ypt']:
        qq=q.dropna(subset=[m,'d_'+m,'o_'+m])
        row['def_r_'+m]=round(np.corrcoef(qq['d_'+m],qq[m])[0,1],3); row['off_r_'+m]=round(np.corrcoef(qq['o_'+m],qq[m])[0,1],3)
        # incremental R2 of defence over offence
        X0=np.c_[np.ones(len(qq)),qq['o_'+m]]; X1=np.c_[X0,qq['d_'+m]]
        r2=lambda X: 1-((qq[m]-X@np.linalg.lstsq(X,qq[m],rcond=None)[0])**2).sum()/((qq[m]-qq[m].mean())**2).sum()
        row['R2off_'+m]=round(r2(X0),3); row['R2both_'+m]=round(r2(X1),3)
    out.append(row)
O=pd.DataFrame(out); pd.set_option("display.width",250)
print(O[['pos','n']+[c for c in O if c.startswith('def_r_')]].to_string(index=False))
print(O[['pos']+[c for c in O if c.startswith('off_r_')]].to_string(index=False))
print(O[['pos']+[c for c in O if c.startswith('R2')]].to_string(index=False))
# tercile effect: actual yards when defence is top-third vs bottom-third allowed (prior)
for pos in ['WR','TE','RB','RUSH']:
    q=A[A.rpos==pos].dropna(subset=['d_yds']).copy(); q['t']=q.groupby(['season','week']).d_yds.transform(lambda s: pd.qcut(s.rank(method='first'),3,labels=['stingy','mid','soft']))
    print(pos, q.groupby('t',observed=True).agg(n=('yds','size'),prior=('d_yds','mean'),actual_yds=('yds','mean'),actual_td=('td','mean')).round(2).to_dict('index'))
