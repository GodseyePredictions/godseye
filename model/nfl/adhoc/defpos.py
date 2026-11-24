import pandas as pd, numpy as np
pd.set_option("display.width",250); pd.set_option("display.max_columns",40)
D='/home/user/attd/data/'
cols=['game_id','season','week','season_type','posteam','defteam','play_type','pass_attempt','complete_pass','sack','receiver_player_id','rusher_player_id','yards_gained','receiving_yards','rushing_yards','yards_after_catch','air_yards','touchdown','td_player_id','td_team','rush_attempt','qb_scramble','two_point_attempt']
def load(y):
    import pyarrow.parquet as pq
    have=set(pq.ParquetFile(D+f'pbp_{y}.parquet').schema.names)
    p=pd.read_parquet(D+f'pbp_{y}.parquet',columns=[c for c in cols if c in have])
    r=pd.read_parquet(D+f'roster_{y}.parquet',columns=['gsis_id','position']).dropna().drop_duplicates('gsis_id').set_index('gsis_id').position
    p=p[(p.season_type=='REG')]
    if 'two_point_attempt' in p: p=p[p.two_point_attempt!=1]
    p['rpos']=p.receiver_player_id.map(r); p['upos']=p.rusher_player_id.map(r); p['tdpos']=p.td_player_id.map(r) if 'td_player_id' in p else np.nan
    p['season']=y
    return p
def tables(p):
    G=p.groupby('defteam').game_id.nunique()
    tg=p[(p.pass_attempt==1)&(p.sack!=1)&p.receiver_player_id.notna()&p.rpos.isin(['WR','TE','RB','FB'])].copy()
    tg['rpos']=tg.rpos.replace({'FB':'RB'})
    a=tg.groupby(['defteam','rpos']).agg(tgt=('pass_attempt','size'),rec=('complete_pass','sum'),yds=('yards_gained',lambda x: x[tg.loc[x.index,'complete_pass']==1].sum()),
        yac=('yards_after_catch',lambda x: x[tg.loc[x.index,'complete_pass']==1].sum()),td=('touchdown',lambda x: ((x==1)&(tg.loc[x.index,'complete_pass']==1)&(tg.loc[x.index,'td_team']==tg.loc[x.index,'posteam'])).sum())).reset_index()
    a['g']=a.defteam.map(G)
    for c in ['tgt','rec','yds','yac','td']: a[c+'_pg']=a[c]/a.g
    a['catch']=a.rec/a.tgt; a['ypr']=a.yds/a.rec; a['ypt']=a.yds/a.tgt; a['yac_pr']=a.yac/a.rec; a['yac_share']=a.yac/a.yds
    ru=p[(p.rush_attempt==1)&(p.upos.isin(['RB','FB']))]
    b=ru.groupby('defteam').agg(car=('rush_attempt','size'),ryds=('yards_gained','sum'),rtd=('touchdown',lambda x: ((x==1)&(ru.loc[x.index,'td_team']==ru.loc[x.index,'posteam'])).sum())).reset_index()
    b['g']=b.defteam.map(G); b['car_pg']=b.car/b.g; b['ryds_pg']=b.ryds/b.g; b['ypc']=b.ryds/b.car; b['rtd_pg']=b.rtd/b.g
    return a,b,G
if __name__=="__main__":
    p=load(2026); a,b,G=tables(p)
    print("games:",G[['IND','HOU']].to_dict(), "weeks through", p.week.max())
    def rk(df,col,asc=False):   # rank 1 = most allowed
        return df[col].rank(ascending=asc,method='min').astype(int)
    for pos in ['WR','TE','RB']:
        q=a[a.rpos==pos].copy()
        for c in ['tgt_pg','rec_pg','yds_pg','yac_pg','catch','ypr','ypt','yac_pr','yac_share','td_pg']: q['r_'+c]=rk(q,c)
        print(f"\n== vs {pos} (receiving) — rank 1 = most allowed of 32; league avg in last row")
        s=q[q.defteam.isin(['IND','HOU'])][['defteam','g','tgt_pg','rec_pg','yds_pg','yac_pg','catch','ypr','ypt','yac_pr','yac_share','td','r_tgt_pg','r_rec_pg','r_yds_pg','r_yac_pg','r_catch','r_ypr','r_ypt','r_yac_pr','r_yac_share','r_td_pg']]
        print(s.round(2).to_string(index=False)); print("LEAGUE", q[['tgt_pg','rec_pg','yds_pg','yac_pg','catch','ypr','ypt','yac_pr','yac_share','td_pg']].mean().round(2).to_dict())
    for c in ['car_pg','ryds_pg','ypc','rtd_pg']: b['r_'+c]=rk(b,c)
    print("\n== vs RB rushing"); print(b[b.defteam.isin(['IND','HOU'])].round(2).to_string(index=False)); print("LEAGUE",b[['car_pg','ryds_pg','ypc','rtd_pg']].mean().round(2).to_dict())
    # TDs allowed by scorer position
    t=p[(p.touchdown==1)&(p.td_team==p.posteam)&p.play_type.isin(['run','pass'])].copy()
    t['kind']=np.where(t.play_type=='pass','rec','rush'); t['tdpos']=t.tdpos.replace({'FB':'RB'}).fillna('other')
    x=t.groupby(['defteam','kind','tdpos']).size().unstack(['kind','tdpos'],fill_value=0)
    x.columns=[f"{k}_{pp}" for k,pp in x.columns]
    x['total']=x.sum(axis=1); x['g']=G
    print("\n== offensive TDs allowed by scorer position"); print(x.loc[['IND','HOU']].to_string())
    lg=x.drop(columns=['g']).div(x.g,axis=0).mean().round(2); print("LEAGUE per game",lg.to_dict())
    xr=x.drop(columns=['g','total']).div(x.g,axis=0)
    for c in xr.columns:
        r=xr[c].rank(ascending=False,method='min').astype(int); print(c,"rank IND",r['IND'],"HOU",r['HOU'], "per game IND",round(xr.loc['IND',c],2),"HOU",round(xr.loc['HOU',c],2))
    # who scored
    rr=pd.read_parquet(D+'roster_2026.parquet',columns=['gsis_id','full_name']).drop_duplicates('gsis_id').set_index('gsis_id').full_name
    for tm in ['IND','HOU']:
        q=t[t.defteam==tm]; print(tm,"by week:",[(int(w),rr.get(i,'?'),pp,k) for w,i,pp,k in zip(q.week,q.td_player_id,q.tdpos,q.kind)])
