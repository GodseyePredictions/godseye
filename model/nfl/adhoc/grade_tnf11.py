import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
INK, MUTED, RED, LINE, BAND = (colors.HexColor(c) for c in ("#161b26","#5b6473","#8b1a2b","#d5d9e0","#f3f5f8"))
ss=getSampleStyleSheet()
T=ParagraphStyle("T",parent=ss["Title"],fontName="Helvetica-Bold",fontSize=20,textColor=INK,alignment=0,spaceAfter=2)
SUB=ParagraphStyle("S",parent=ss["Normal"],fontSize=8.5,textColor=MUTED,leading=11)
H2=ParagraphStyle("H2",parent=ss["Heading2"],fontName="Helvetica-Bold",fontSize=13,textColor=INK,spaceBefore=10,spaceAfter=4)
B=ParagraphStyle("B",parent=ss["Normal"],fontSize=9,textColor=INK,leading=12,spaceAfter=3)
SM=ParagraphStyle("SM",parent=B,fontSize=8.2,leading=10.5); HD=ParagraphStyle("HD",parent=SM,fontName="Helvetica-Bold",textColor=colors.white)
P=lambda t,s=B: Paragraph(t,s)
def tbl(rows,widths):
    rows=[[P(str(c),HD) for c in rows[0]]]+[[P(str(c),SM) for c in r] for r in rows[1:]]
    t=Table(rows,colWidths=[w*inch for w in widths],repeatRows=1)
    st=[("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),0.25,LINE),("BACKGROUND",(0,0),(-1,0),RED),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
    st+=[("BACKGROUND",(0,i),(-1,i),BAND) for i in range(2,len(rows),2)]; t.setStyle(TableStyle(st)); return t
OK="<font color='#1f6f3f'><b>HIT</b></font>"; NO="<font color='#8b1a2b'><b>MISS</b></font>"
LAB={"atd":"anytime TD","rec":"receptions","rec_yds":"rec yds","rush_yds":"rush yds","carries":"carries","pass_att":"pass att","pass_yds":"pass yds","pass_td":"pass TDs"}
J=json.load(open('/home/user/attd/outputs/internal/graded_2026_wk11_tnf.json'))
story=[P("Report card · Week 11 TNF · Texans 26, Colts 3",T),P("Graded as shipped from the locked official record (outputs/official). 13 tickets, 26 unique legs. Compared with a model-only build using the same inactives.",SUB),Spacer(1,6),
 P("Result",H2),
 tbl([["Slip","Priced","Legs hit","Missed"]]+[[a,f"{b:.1%}",f"{c} of {d}",", ".join(e) if e else "none"] for a,b,c,d,e in J["official"]],[1.6,0.7,0.8,3.9]),
 P("No ticket cashed against 2.0 expected. Props legs 12 of 22 (55%) against 76% priced. Anytime-TD legs 1 of 4 against 1.6 expected. The lotto went 8 of 9.",B),
 P("Every leg",H2)]
rows=[["Leg","Model","Actual","Result"]]
for n,m,k,p,h,v in J["official_legs"]: rows.append([f"<b>{n}</b> {str(k)+'+ ' if k else ''}{LAB[m]}",f"{p:.0%}",f"{v} TD" if m=="atd" else v,OK if h else NO])
story+=[tbl(rows,[3.6,0.8,1.2,1.4]),PageBreak(),
 P("Official build against the model-only build",H2),
 tbl([["","Official (matchup reads on)","Model only"],["Props legs","12 of 22","12 of 18"],["Props 6-leg","2 of 6","4 of 6"],["6-leg, 1 anytime TD","3 of 6","4 of 6"],["Lotto","8 of 9","7 of 9"],["Tickets cashed","0","0"]],[2.2,2.4,2.4]),
 P("What the reads changed: they dropped Stroud 200+ pass yards (right, he threw for 194), dropped Stroud 2+ pass TDs (wrong, he threw 3) and dropped Warren 20+ yards (wrong, he had 22). They added Taylor 10+ carries (hit), Daniel Jones 1+ pass TD (miss) and Collins 4+ receptions (miss), and pushed Taylor 30+ rush yards, the read I called strongest at 9 of 9, into every recommended slip (miss, 21 yards). Net: no better than the model, slightly worse on the mid-length slips. One game, and consistent with the backtest that said these splits carry little.",B),
 P("Grades",H2),
 tbl([["Area","Grade","Why"],
  ["Nico Collins","A","Touchdown, 3 catches, 58 yards. Top of the scorer board at 46% and the right single."],
  ["David Montgomery role call","A-","26 carries for 107 and 3 catches with Marks out. All four of his lines hit, including two on the Aggressive slip. The model had him at 8.8 carries; the role read was mine and it was right. He did not score, which cost the double."],
  ["Texans passing legs","B+","Stroud 1+ TD and 25+ attempts hit, Collins 40+ yards and 3+ catches hit. Stroud 200+ yards missed by 6 and the reads had already removed it."],
  ["Colts offence legs","F","Warren 3+ catches (1 catch on 5 targets), Taylor 30+ rush (21 yards on 11 carries), Jones 1+ TD (0). The Colts ran 48 plays, went 1 of 11 on third down and scored 3 points. Warren 3+ catches alone was on 10 of 13 tickets and killed the lotto at 8 of 9."],
  ["My own warnings","D","I said three separate times that the new Colts offence was unproven and that Warren's numbers came from the old one. I removed only his yardage leg and kept the catches leg on every slip. The warning was right and I did not act on it."],
  ["Matchup reads","D","No gain over the model in their first live test, and their strongest call (Taylor rushing) missed."],
  ["Slip construction","C-","The one-script cap worked as designed, but half of each ticket then sat on a 12.5-point underdog with a gutted offence. Third straight prime-time game where the losing side's legs sank the slips."],
  ["Process","A-","Inactives caught and applied, total updated, Montgomery found by the returning-player fix, release locked and graded from the record."],
  ["Overall","D+","Good reads on the Texans, undone by legs on the Colts that I had already said I did not trust."]],[1.7,0.6,4.7]),
 P("What I would change, not yet applied",H2),
 P("<b>1. Heavy-underdog offence limit.</b> When a team is a double-digit underdog with an implied total under about 17, cap its legs at two per ticket and take only attempt-volume legs (Jones 20+ attempts hit; everything needing Colts production missed). Needs a backtest before it becomes a rule.",B),
 P("<b>2. Changed-offence flag.</b> When a team loses 25%+ of its targets to trades or injury inside two weeks, treat its remaining pass-catchers like returning players: singles only until two games are on record.",B),
 P("<b>3. Role override for a confirmed lead back.</b> When the starter is out and the replacement is confirmed, the 3-of-5 hit-rate gate should not block his volume legs. Montgomery's 20+ and 30+ rush were the best legs in the game and the standard slips could not use them.",B),
 P("<b>4. Matchup reads off.</b> Keep the code as experimental and do not use it on official slips. Keep the run-defence signal, which the model already carries.",B)]
SimpleDocTemplate("/home/user/attd/outputs/internal/Report_Card_2026_Wk11_TNF.pdf",pagesize=letter,leftMargin=0.6*inch,rightMargin=0.6*inch,topMargin=0.6*inch,bottomMargin=0.6*inch).build(story); print("ok")
