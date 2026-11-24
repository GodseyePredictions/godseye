import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
LAB={"atd":"anytime TD","rec":"receptions","rec_yds":"rec yds","rush_yds":"rush yds","pass_att":"pass att","pass_yds":"pass yds"}
J=json.load(open('/home/user/attd/outputs/internal/graded_2026_wk10_mnf.json'))
story=[P("Report card · Week 10 MNF · Chargers 23, Ravens 20",T),P("Graded as shipped against official stat lines. Four slips, 10 unique legs.",SUB),Spacer(1,6),
 tbl([["Slip","Legs hit","Result"]]+[[k,f"{sum(x[5] for x in v)} of {len(v)}","<font color='#8b1a2b'><b>LOST</b></font>"] for k,v in J.items()],[4.2,1.2,1.6]),Spacer(1,6)]
legs={}
for v in J.values():
    for x in v: legs[(x[0],x[1],x[2])]=x
rows=[["Leg","Model","Actual","Result"]]
for x in legs.values(): rows.append([f"<b>{x[0]}</b> {x[2]+'+ ' if x[2] else ''}{LAB[x[1]]}",f"{x[3]:.0%}",f"{x[4]} TD" if x[1]=="atd" else x[4],OK if x[5] else NO])
story+=[P("Every leg",H2),tbl(rows,[3.6,0.8,1.2,1.4]),
 P("What happened",H2),
 P("Both touchdown legs hit: Henry scored twice and Hampton once. The slips died on the props. The read was the Chargers trailing and throwing. They led and ran instead: Hampton carried 22 times for 105 and Herbert threw 18 passes for 129 yards. Baltimore, with Jacoby Brissett starting, threw 49 times. Five of the eight prop legs rode the Chargers' passing volume and went down together. Two more were depth receptions (Lambert-Smith, who was 2 of 3 on the season, and Keaton Mitchell) that never had a real role.",B),
 P("Grades",H2),
 tbl([["Area","Grade","Why"],
  ["Anytime-TD legs","A","2 of 2. Henry at the haircut price of 43% and Hampton at 32% both scored."],
  ["Props legs","F","3 of 8 against 75% priced. Not bad luck: one script, and the wrong one."],
  ["Slip construction","F","Every prop leg came from one team and five from one passing game. I flagged the risk in writing and shipped it anyway."],
  ["Quarterback read","C","The backup-QB flag on Baltimore was right, but the build assumed Fagnano. Brissett started and threw for 340."],
  ["Overall","D","Right scorers, wrong ticket."]],[1.6,0.6,4.8]),
 P("Fixed for Thursday",H2),
 P("<b>1. One-script cap.</b> Legs tied to one team's passing game can be at most half of any ticket, at every length.",B),
 P("<b>2. Minimum sample.</b> A prop leg needs at least four games on record this season.",B),
 P("<b>3. Returning players re-enter the pool.</b> A player with no snaps in the last four games who is practising this week is now projected, flagged as returning. Found while building Thursday (David Montgomery); the same hole hid Travis Etienne on Sunday.",B)]
SimpleDocTemplate("/home/user/attd/outputs/internal/Report_Card_2026_Wk10_MNF.pdf",pagesize=letter,leftMargin=0.6*inch,rightMargin=0.6*inch,topMargin=0.6*inch,bottomMargin=0.6*inch).build(story); print("ok")
