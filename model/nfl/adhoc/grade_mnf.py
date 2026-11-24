from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from datetime import datetime, timezone
INK, MUTED, RED, LINE, BAND = (colors.HexColor(c) for c in ("#161b26","#5b6473","#8b1a2b","#d5d9e0","#f3f5f8"))
ss=getSampleStyleSheet()
T=ParagraphStyle("T",parent=ss["Title"],fontName="Helvetica-Bold",fontSize=20,textColor=INK,alignment=0,spaceAfter=2)
SUB=ParagraphStyle("S",parent=ss["Normal"],fontSize=8.5,textColor=MUTED,leading=11)
H2=ParagraphStyle("H2",parent=ss["Heading2"],fontName="Helvetica-Bold",fontSize=13,textColor=INK,spaceBefore=10,spaceAfter=4)
B=ParagraphStyle("B",parent=ss["Normal"],fontSize=9,textColor=INK,leading=12,spaceAfter=3)
SM=ParagraphStyle("SM",parent=B,fontSize=8.2,leading=10.5)
HD=ParagraphStyle("HD",parent=SM,fontName="Helvetica-Bold",textColor=colors.white)
def P(t,s=B): return Paragraph(t,s)
def tbl(rows,widths):
    rows=[[P(c,HD) if isinstance(c,str) else c for c in rows[0]]]+[[P(c,SM) if isinstance(c,str) else c for c in r] for r in rows[1:]]
    t=Table(rows,colWidths=widths,repeatRows=1)
    st=[("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),0.25,LINE),("BACKGROUND",(0,0),(-1,0),RED),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
    st+=[("BACKGROUND",(0,i),(-1,i),BAND) for i in range(2,len(rows),2)]
    t.setStyle(TableStyle(st)); return t
OK="<font color='#1f6f3f'><b>HIT</b></font>"; NO="<font color='#8b1a2b'><b>MISS</b></font>"
def leg(n,txt,p,act,hit): return [f"{n}. {txt}",p,act,OK if hit else NO]
def res(r): return f"<font color='{'#1f6f3f' if r=='CASHED' else '#8b1a2b'}'><b>{r}</b></font>"

story=[P("Internal report card · Week 9 MNF · Bills @ Vikings",T),
 P(f"Self-grades on the shipped SGP picks (pregame refresh, built Nov 10 00:04 UTC). Graded as shipped against the official nflverse stat lines "
   f"pulled {datetime.now(timezone.utc):%b %-d %H:%M} UTC. Internal only: not on the site, not in the public ledger.",SUB),Spacer(1,6)]
story+=[P("Result",H2),
 tbl([["","Shipped read","Actual"],
      ["Score","BUF favoured by 3.5 (implied 24.5), MIN implied 21.0, total 45.5","BUF 23, MIN 6. Total 29, 16.5 under the number"],
      ["Script","Buffalo control, run-leaning; Vikings throw 70% when behind","Buffalo controlled everything: 79 real plays to 46, possession 42:32 to 17:28"],
      ["Vikings QB","Wentz starts (Murray out)","Wentz 8/25, 81 yds, 2 INT; benched for Brosmer (6/7, 58 yds)"],
      ["Third downs","MIN drives die on 3rd down","MIN 0 of 8 on 3rd down; BUF 7 of 18"],
      ["Penalties","(tempo & discipline group not live for this game)","BUF 8 for 62 (five false starts), MIN 4 for 20"],
      ["TD scorers","Cook 55%, Allen 41%, Jefferson 38%, Jones 33%, ...","Two touchdowns all game: Cook (rush) and Keleki Latu (TE3, not on the board)"]],
     [1.0*inch,2.9*inch,3.1*inch])]
story+=[P("Script-first SGP slip (props)",H2)]
L4=[leg(1,"Khalil Shakir 2+ receptions","86%","4 rec",1),leg(2,"Josh Allen 20+ pass att","85%","31 att",1),
    leg(3,"Jordan Addison 2+ receptions","82%","2 rec (exactly)",1),leg(4,"Jordan Addison 20+ rec yds","79%","28 yds",1)]
L6=L4+[leg(5,"James Cook 50+ rush yds","79%","107 yds",1),leg(6,"Justin Jefferson 30+ rec yds","82%","58 yds",1)]
L8=L6+[leg(7,"Justin Jefferson 4+ receptions","74%","3 rec on 11 targets",0),leg(8,"Khalil Shakir 20+ rec yds","73%","58 yds",1)]
L10=L8+[leg(9,"Josh Allen 175+ pass yds","74%","234 yds",1),leg(10,"Jordan Mason 20+ rush yds","70%","35 yds",1)]
H1=[leg(1,"James Cook anytime TD","55%","rush TD 4Q 6:21",1),leg(2,"James Cook 50+ rush yds","79%","107 yds",1),
    leg(3,"Jordan Addison 2+ receptions","82%","2 rec",1),leg(4,"Jordan Addison 20+ rec yds","79%","28 yds",1),leg(5,"Khalil Shakir 2+ receptions","86%","4 rec",1)]
H2L=[H1[0],leg(2,"Josh Allen anytime TD","41%","no TD (1 pass TD, 15 rush yds)",0)]+[[f"{i+3}. "+r[0][3:]]+r[1:] for i,r in enumerate(H1[1:])]
tix=[("4-leg · 53.7% · fair -116",L4,"CASHED"),("6-leg · 34.7% · fair +188",L6,"CASHED"),
     ("8-leg · 23.8% · fair +320",L8,"MISS (7 of 8)"),("10-leg · 13.8% · fair +626",L10,"MISS (9 of 10)"),
     ("Hybrid 1 ATD + 4 props · 29.4% · fair +240",H1,"CASHED"),("Hybrid 2 ATD + 4 props · 12.1% · fair +723",H2L,"MISS (5 of 6)")]
story.append(tbl([["Ticket","Result"]]+[[t[0],res(t[2])] for t in tix],[4.6*inch,2.4*inch]))
story.append(Spacer(1,4))
story.append(P("Unique legs: 12 props, 11 hit (92%) against 78% average shipped probability. Two anytime-TD legs, 1 hit (50%) against 48% shipped. "
  "The single miss, Jefferson 4+ receptions, was the thinnest leg on the ladder and lost to Wentz accuracy (3 catches on 11 targets), not to volume.",B))
for name,legs,r in tix:
    story.append(P(f"<b>{name}</b> · {res(r)}",SM))
    story.append(tbl([["Leg","p","Actual","Result"]]+legs,[3.0*inch,0.6*inch,2.2*inch,1.2*inch])); story.append(Spacer(1,3))
story+=[PageBreak(),P("ATD slip (board and in-game combos)",H2)]
board=[("James Cook","RB BUF","55%","-120","rush TD",1),("Josh Allen","QB BUF","41%","+144","no TD",0),("Justin Jefferson","WR MIN","38%","+162","no TD",0),
 ("Aaron Jones","RB MIN","33%","+202","no TD · 5 carries",0),("Jordan Addison","WR MIN","31%","+223","no TD",0),("T.J. Hockenson","TE MIN","28%","+255","no TD",0),
 ("DJ Moore","WR BUF","27%","+274","no TD",0),("Jordan Mason","RB MIN","24%","+314","no TD",0),("Dalton Kincaid","TE BUF","23%","+338","no TD",0),
 ("Keon Coleman","WR BUF","22%","+353","no TD",0),("Khalil Shakir","WR BUF","18%","+455","no TD",0),("Ty Johnson","RB BUF","13%","+669","no TD",0),("Dawson Knox","TE BUF","12%","+705","no TD",0)]
story.append(tbl([["#","Player","p","Fair","Actual","Result"]]+[[str(i+1),f"{a} · {b}",c,d,e,OK if h else NO] for i,(a,b,c,d,e,h) in enumerate(board)],[0.3*inch,2.2*inch,0.6*inch,0.6*inch,2.0*inch,1.3*inch]))
story.append(Spacer(1,4))
story.append(P("Board: 1 of 13 hit. The board summed to 3.65 expected scorers; the game produced 2 touchdowns, one by a player under the 10% floor (Latu). "
  "All four in-game combos (Cook+Allen 22.4%, Cook+Jones 18.5%, Allen+Jones 14.0%, 3-leg 7.8%) missed on Allen and Jones. "
  "Card ATD legs across the week graded 1 of 16 (6% actual vs 24% expected).",B))
story+=[P("Grades",H2),
 tbl([["Area","Grade","Why"],
  ["Game-script read","B+","Direction right (Buffalo control, Vikings forced to throw, drives dying on 3rd down). Magnitude understated: a 42-minute possession edge and a 29-point total were far outside the mid-total script. The 'underdogs throw to catch up' volume thesis for Addison and Jefferson cleared its floors by the minimum."],
  ["Props ladder","A-","4 and 6 cashed at fair -116 and +188. 8 and 10 missed by one leg each, the leg ranked weakest on the ladder. 11 of 12 unique legs hit against a 78% average shipped probability; outcome ran hot, not wrong."],
  ["Hybrids","B+","1 ATD + 4 cashed at +240. 2 ATD + 4 missed on Allen anytime TD at 41%: a fair miss in a one-rushing-TD game."],
  ["ATD board","D","1 of 13, four combos 0 for 4. Priced off a 45.5 total; the game scored 29. The whole board over-priced the Vikings side (Jefferson, Jones, Addison, Hockenson, Mason: 0 for 5 with Wentz 8 of 25). The lesson is not calibration in general but that a backup QB starting on the road should cut every teammate's ATD probability, and the model has no explicit QB-quality downgrade for that."],
  ["Personnel and news","C+","Pregame ESPN scratches were caught and applied. Jordan Mason's return was caught only after the user flagged it (rule fixed since). Wentz benched for Brosmer mid-game is not a pregame catch."],
  ["Tempo & discipline (new, not live for this game)","n/a","Would have read 63 / 60 plays and 31:45 / 28:58 possession; actual 79 / 46 real plays, 42:32 / 17:28. Right direction, nowhere near the magnitude. Buffalo's eight flags (five false starts) did not stop them. Evidence the group tilts scripts correctly but will not catch a blowout on its own."],
  ["Interceptions read (assessment only)","A","Allen ~58% to throw one (threw 1), Wentz ~48% (threw 2). Both would have hit; no engine market existed to ship it."],
  ["Overall","B-","Props side was the strongest shipped slate of the season; ATD side was the weakest. A one-sided blowout with a backup QB is the game that breaks a Vegas-anchored TD board."]],
  [1.6*inch,0.6*inch,4.8*inch])]
story+=[P("Actions logged",H2),
 P("1. Add a backup-QB penalty to teammate ATD probabilities (starter out, replacement with few starts this season) and backtest it before Week 10 ships final.",B),
 P("2. Cap the ATD slip's single-game combos at two legs when a team starts a backup QB; the 3-leg combo was dead on the Vikings side.",B),
 P("3. Re-run the four unfinished tempo backtest markets on a quiet container.",B),
 P("4. Public ledger untouched; this card stays in outputs/internal.",B)]
SimpleDocTemplate("outputs/internal/Grade_2026_Wk9_MNF_BUF_MIN.pdf",pagesize=letter,leftMargin=0.6*inch,rightMargin=0.6*inch,topMargin=0.6*inch,bottomMargin=0.6*inch,title="Internal grade Wk9 MNF").build(story)
print("ok")
