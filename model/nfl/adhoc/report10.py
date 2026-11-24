import json, pandas as pd
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
P=lambda t,s=B: Paragraph(t,s)
def tbl(rows,widths):
    rows=[[P(str(c),HD) for c in rows[0]]]+[[P(str(c),SM) for c in r] for r in rows[1:]]
    t=Table(rows,colWidths=[w*inch for w in widths],repeatRows=1)
    st=[("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,-1),0.25,LINE),("BACKGROUND",(0,0),(-1,0),RED),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]
    st+=[("BACKGROUND",(0,i),(-1,i),BAND) for i in range(2,len(rows),2)]
    t.setStyle(TableStyle(st)); return t
G="<font color='#1f6f3f'><b>%s</b></font>"; R="<font color='#8b1a2b'><b>%s</b></font>"
J=json.load(open('/home/user/attd/outputs/internal/graded_2026_wk10_sunday.json')); TK=J["tickets"]
story=[P("Report card · Week 10 Sunday · God's Eye",T),
 P(f"Self-grade on every slip shipped Sunday Nov 15 (early, afternoon and evening). Graded as shipped against official nflverse stat lines pulled {datetime.now(timezone.utc):%b %-d %H:%M} UTC. 59 tickets, 115 unique legs.",SUB),Spacer(1,6),
 P("The short version",H2),
 P("The props legs landed on their numbers. The anytime-TD legs ran a little under, with running backs on target and pass-catchers cold. Ten of 59 tickets cashed against 13.3 expected. The week felt worse than the legs were because most of what I shipped was long anytime-TD parlays, and those lose almost every time by construction. One real model error showed up and is now fixed: teammates of backup quarterbacks were overpriced for touchdowns.",B),
 P("Legs",H2),
 tbl([["Leg type","Legs","Hit","Expected","Read"],
  ["Props, all markets","83","65 (78.3%)","79.2%","On target"],
  ["· receptions","26","73.1%","79.6%","Cold; one week of 26 legs, holdout says calibrated"],
  ["· pass attempts / pass yards","18","88.9%","80.5%","Hot"],
  ["· rec yds / rush yds / carries / pass TDs","39","76.9%","78.3%","On target"],
  ["Anytime TD, backs and QBs","20","10","9.6","On target"],
  ["Anytime TD, receivers and tight ends","12","3","4.7","Cold"],
  ["Pass-catcher singles board","18","5","7.1","Cold"]],[2.3,0.6,1.0,0.8,2.3]),
 P("Whole Sunday board, every player who took the field: running backs 16.5 touchdowns scorers expected and 18 actual, receivers 18.7 and 20, tight ends 9.6 and 8, quarterbacks 3.1 and 3. The model's probabilities were right in aggregate.",SM),
 P("Tickets",H2)]
df=pd.DataFrame(TK); df["away"]=df.n-df.hits
rows=[["Ticket type","Shipped","Cashed","Expected to cash","One leg short"]]
for k in ["ATD ticket","ATD mixed","Hybrid 1 ATD","Hybrid 2 ATD","Props 4-leg","Props 6-leg","Props 8-leg"]:
    q=df[df.kind==k]; rows.append([k,len(q),int(q.cashed.sum()),f"{q.p.sum():.1f}",int((q.away==1).sum())])
rows.append(["<b>All</b>",len(df),int(df.cashed.sum()),f"{df.p.sum():.1f}",int((df.away==1).sum())])
story+=[tbl(rows,[2.2,1.0,1.0,1.4,1.4]),
 P("Cashed: early 4-leg ATD (Cook, Bijan Robinson, Pollard, Hubbard; 9.3%, fair +973), KC @ ATL props 4, 6 and 8-leg and its 1-ATD 8-leg, JAX @ TEN 4-leg, SF @ DAL props 4, 6 and 8-leg and its 1-ATD 8-leg.",SM),
 P("Legs that killed the most tickets: Woody Marks TD (7 tickets), Jonathan Taylor TD (5), Javonte Williams TD (5), Kyren Williams TD (5), Chris Olave TD (5), Dalton Schultz 2+ receptions (5, caught 1), Tucker Kraft 2+ receptions (5, caught 1), Bryce Young 1+ pass TD (5), Jalen Coker 2+ receptions (5, caught 0), Geno Smith 150+ pass yards (5, threw for 148).",SM),
 P("Grades",H2),
 tbl([["Area","Grade","Why"],
  ["Props legs","B+","78.3% against 79.2% priced over 83 legs. Calibrated."],
  ["Props tickets","C+","7 of 27 cashed against 10.1 expected; nine more were one leg short. Two games carried it (KC @ ATL, SF @ DAL). CAR @ NO, rated the strongest 4-leg at 58%, went 2 of 4."],
  ["ATD legs, backs and QBs","B","10 of 20 against 9.6 expected. The early 4-leg cashed. The afternoon 4-leg lost three of four, including two backs priced over 60%."],
  ["ATD legs, pass-catchers","D","3 of 12 on tickets and 5 of 18 as singles. Every hybrid that used a receiver or tight end as its TD leg lost that leg except one."],
  ["ATD ticket design","D","I shipped twelve ATD-only parlays; eight of them were priced under 2%. A 10-leg at 0.05% cashes once in about 2,000 tries. Those are lottery tickets and I presented them next to real plays."],
  ["Exceptions I added on Sunday","F","To fill the 6, 8 and 10-leg tickets I bent my own hold-outs: backs on backup-QB offences (Charbonnet, Jeanty, Allgeier) went 0 for 3, Breece Hall missed, Emmett Johnson hit. The rule existed for a reason and the data backs it."],
  ["Backup-QB handling","B-","Holding those offences off tickets was right (Arizona 6 points, Las Vegas 13). But the board still priced their players at full value, which is the model error fixed below."],
  ["News and inactives","A-","ESPN sweep and game-day rosters caught Walker, Montgomery, Watson, Garrett Wilson, Addison, Pickens before kickoff. The first PDFs went out before inactives and had to be replaced."],
  ["Game scripts","C","Four more blowouts the script read as close: KC by 22 as a 3-point favourite, MIN by 20 in a pick'em, LA by 28, CIN by 20 as an underdog. Volume legs on the losing side paid for it (Geno Smith, Warren)."],
  ["Overall","C+","Sound probabilities, poor ticket construction, one genuine pricing error."]],[1.9,0.6,4.5]),
 PageBreak(),P("What I fixed, with the evidence",H2),
 P("<b>1. Backup-quarterback haircut, now in the model.</b> Out of sample across 2025 and 2026 (weeks 4 on), when a team's starter had thrown under 25% of its passes that season, his teammates priced at 20% or better scored far less than priced.",B),
 tbl([["Group","Player-games","Priced","Actual","Gap"],
  ["Receivers and tight ends, backup QB","133","28.6%","17.3%","-11.3 pts (standard error 3.2)"],
  ["Running backs, backup QB","96","38.3%","31.2%","-7.1 pts (standard error 4.7)"],
  ["Running backs priced 30%+, backup QB","65","44.9%","29.2%","-15.7 pts"],
  ["Receivers and tight ends, regular starter","1,260","31.8%","32.5%","+0.7 pts"],
  ["Running backs, regular starter","704","42.9%","43.5%","+0.6 pts"]],[2.8,1.0,0.8,0.8,1.6]),
 P("The projection now shifts those teammates down on the log-odds scale (receivers and tight ends by 0.5, backs by 0.3, shrunk from the raw estimates for sample size). A receiver the model had at 40% behind a backup is now 29%; a back at 45% is now 38%. The quarterback's own number is unchanged.",SM),
 P("<b>1b. Backup-quarterback detection.</b> The detector only read the weekly injury report, so it missed Baltimore, whose first two quarterbacks are on injured reserve. It now also flags any team whose expected starter has thrown under 25% of its passes this season, the same definition the haircut was measured on.",B),
 P("<b>2. No more backup-QB backs as fill legs.</b> The third exception tier is deleted. If the clean pool runs out, the ticket size is skipped.",B),
 P("<b>3. Hybrids pick a back first.</b> The anytime-TD leg in a same-game slip is now ranked on the play-at probability (model minus the position cushion: backs 3 points, tight ends and quarterbacks 4, receivers 6). A pass-catcher is only the TD leg when he clears the backs by more than his cushion.",B),
 P("<b>4. Tickets are now saved as shipped.</b> Window packs and script slips are written to the shipped-tickets snapshot on every build, so grading reads the exact tickets instead of parsing PDFs.",B),
 P("<b>5. Tested and rejected: shrinking the top of the board.</b> Receivers priced 40%+ hit 39% against a 46% price over the full sample, which looked like a fix. Fitted on 2025 and tested on 2026 it did not help (2026 log loss 0.3927 raw, 0.3933 adjusted; five-fold gain +0.00004 with an interval spanning zero), and 2026 on its own shows no gap. Not applied. The 6-point receiver cushion on the play-at price already covers it.",B),
 P("What I did not fix",H2),
 P("• <b>Blowouts.</b> The script still reads spread and total from the market and cannot see a 20-point game coming. This is two weeks running. The honest position is that nobody prices these, but volume legs on underdogs deserve a wider floor and I have not built or tested that yet.",B),
 P("• <b>Long ATD parlays.</b> I can label them, I cannot make them likely. Six independent 50% legs is 1.6%. The plays with real hit rates are singles at the play-at price, the 4-leg, and the 1-ATD same-game slips.",B),
 P("• <b>Backup-QB props.</b> The haircut is on touchdowns only. Passing and receiving props for those offences stay off tickets by rule; their pricing has not been tested.",B)]
SimpleDocTemplate("/home/user/attd/outputs/internal/Report_Card_2026_Wk10_Sunday.pdf",pagesize=letter,leftMargin=0.6*inch,rightMargin=0.6*inch,topMargin=0.6*inch,bottomMargin=0.6*inch,title="Report card Wk10").build(story)
print("ok")
