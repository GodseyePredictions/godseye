"""Splice the NBA data from a fresh build into the live artifact source.
usage: splice_nba.py LIVE.html FRESH_BUILD.html OUT.html
LIVE is the saved copy of the published artifact (with or without the publish wrapper)."""
import sys,re
def match(s,i):
    d=0;q=None
    while True:
        c=s[i]
        if q:
            if c=='\\': i+=1
            elif c==q: q=None
        elif c in '"\'`': q=c
        elif c=='{': d+=1
        elif c=='}':
            d-=1
            if d==0: return i+1
        i+=1
def region(s):
    a=s.index('={run_at:"20')+1
    e1=match(s,a)
    m=re.match(r';var [\w$]+=',s[e1:e1+20]); assert m and s[e1+m.end():].startswith('{made_at:'), s[e1:e1+30]
    b=e1+m.end()
    return a,e1,b,match(s,b)
live=open(sys.argv[1]).read(); mine=open(sys.argv[2]).read()
la,le,lb,lf=region(live); ma,me,mb,mf=region(mine)
out=(live[:la]+mine[ma:me]+live[le:lb]+mine[mb:mf]+live[lf:]).split("\n")
if out[0].startswith('<!doctype html><html><head>') and out[-1]=='</body></html>': out=out[1:-1]
open(sys.argv[3],'w').write("\n".join(out)); print(len("\n".join(out)))
