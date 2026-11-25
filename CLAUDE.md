# Godseye Predictions

Godseye is a paid sports betting prediction platform. Subscribers log in, see algo picks, get their own bet slips audited, size bets with a bankroll engine, and talk to a 1-to-1 chat advisor. NFL first, NBA next, CFB after.

## One algorithm per sport

Each sport has its own algorithm. NFL has its own, NBA has its own, CFB will have its own. They are separate from one another.

- **Code:** NFL lives in `model/*.py` (plus the imported console in `public/console`). NBA lives in `model/nba/`. NHL lives in `model/nhl/`. None imports another. Only sport-neutral helpers (HTTP, odds maths, odds feed, ticket search) go in `model/common/`.
- **Rules:** ticket rules, probability floors and book formats are per sport. A rule in one sport's section does not apply to another sport unless that sport's section says so. When the two disagree, the section for the sport being worked on wins.
- **Output:** each algorithm writes its own output. A pick shown under a sport comes only from that sport's algorithm.
- **Changes:** work on one sport must not change or break another sport's code, config or output.

The "Platform rules" below apply to every sport.

## Platform rules (all sports)

### Non-negotiable product rules

- **Algo picks only.** Every pick, leg, swap or add comes from the Godseye algorithm for that sport. No expert, media or consensus picks. Web lookups are for official injuries, inactives and rosters only.
- **The LLM never does the math.** Claude reads screenshots, calls tools and explains results. Probabilities, edges, correlations and stakes come only from the Python algos and the staking engine. If a tool doesn't return a number, the agent doesn't state one.
- **Unrated means unrated.** A leg the algo doesn't cover is labelled "unrated". Never guess.

### Staking

- Users set a bankroll and a risk profile. Stakes are shown in units and dollars, e.g. "1.5u ($15)".
- Sizing is quarter-Kelly using algo probabilities, capped by the profile's max per bet and max nightly exposure.
- Unit size is recalculated weekly, not after every loss.
- One shared staking module is the only source of stake numbers. UI and chat agent both call it.

### Responsible gambling

- Never promise wins or "guaranteed" nights. Copy says "bet smarter, survive the variance".
- Support user-set stop-loss, profit lock, nightly exposure caps and cool-off.

### Publishing the site (owner, 24 November 2026)

The published site is https://claude.ai/artifact/SZGmtu64mAZsvzS7y2Hbxw. Every publish, from any session, for any sport, must be the same site with the same design:

- **One build.** Pull main, then `node scripts/build-preview.mjs <file>` and publish that file to that link. Never publish an older saved file, a patched copy, or a page built some other way.
- **One home page.** The landing page (`src/app/(site)/page.tsx`) is always the home page, refreshed with the latest algorithm output.
- **One look.** The Godseye branding, the dark ground, and white slips with red titles and black type (`src/styles/slip.css`, `src/components/Slip.tsx`). New screens reuse these; they do not bring their own styles.
- **Tickets are set slips.** Every algorithm ticket is shown as a slip with its legs, its chance to hit and its chance to miss. A button that only loads the bet slip is not a ticket. In the NFL console use `geSlip` (added by `scripts/import-console.py`).
- **Check before publishing.** Open the built file, confirm the landing page, both consoles and the slips render with no page errors, then publish. If the build or a check fails, do not publish.
- A change to the design is made in the repository and merged to main first, so the next publish from any session carries it.

### Engineering

- Explore the existing repo and reuse what's there before adding new structure.
- Keep algos (Python) separate from the web app. The web app reads algo output from the database.
- Write tests for all math (staking, grading, slip parsing validation).
- Never commit secrets. Use environment variables.
- Commit after each working feature with a clear message.

## NFL algorithm: standing rules

These rules apply to the NFL algorithm only.

### Ticket rules

- SGP legs default to floor milestone rungs with roughly 70%+ hit probability. Edge rungs are for straight singles only.
- At most one leg under 65% on any ticket.
- Props SGPs (props and INTs only) are kept separate from anytime-TD tickets. Never mix TD legs into a props SGP.
- Analyze the full game script and blowout risk before setting any props.
- SGPs consider player props from both teams and take the best legs regardless of side.
- Always factor defensive personnel availability, OC/DC scheme tendencies, and home/away, turf/grass, dome/open-air and weather splits.
- Anytime-TD picks are driven by defensive matchups and red-zone usage, not recent scoring.

### bet365 milestone format

- Player props are one-sided milestone ladders (e.g. 150+/175+/200+ pass yds), not over/unders.
- Rungs come in steps of 5. Rushing and receiving yards ladders start at 20+.
- Only suggest rungs the book actually offers.

## CFB algorithm: standing rules

Not built yet. It will be its own algorithm with its own rules. Until the owner sets them, it starts from the NFL ticket rules and bet365 milestone format, with these differences:

- CFB ladders have no receptions markets and no low rushing rungs.
- Only suggest rungs the book actually offers.

## NHL engine: standing rules

NHL engine spec lives in `model/nhl/SPEC.md` (the spec calls this `godseye/nhl/`). Always read and follow it for any NHL work. The NHL engine is standalone: never import from NFL or NBA model code (`model/*.py`, `model/nfl/`, `model/nba/`); reuse only `model/common/` (the spec's `godseye/shared/`).

- All five phases are built as a test build (owner, 24 November 2026: build it out, publish, test and grade). What is built and how it runs is in `model/nhl/README.md`.
- **Test slips until validated.** No NHL market has been tested against closing lines (no historical prices are held), so the site labels NHL slips as test slips and suggests no stake on props.
- **Paper mode.** With no prop ladder connected, legs use the spec's standard milestone rungs and are marked "rung not verified". Never present such a rung as one the book offers.
- **Results are not posted on the site**, with one exception below. Grading is logged in `model/nhl/output/` and reported to the owner in chat.

### Amendments (24 November 2026, from the owner)

- **Slips per game: a 4-leg, a 6-leg and an 8-leg**, with props and game lines combined on one slip. Markets considered: shots, goals, points, assists, hits, blocks, saves, moneyline, puck line, total. (The spec kept props SGPs and game lines apart and had no 8-leg.) Every leg is still a floor rung; the anytime-scorer slip stays.
- **Multi-game slips:** one 2-game slip and one 3-game slip from the games the model reads best, and one **lotto ticket** at +5000 or longer on the model's fair price, built from longshot rungs. The lotto is the only slip that uses legs under the floor.
- **Every pick carries its breakdown:** the numbers behind it, written by `model/nhl/explain.py` from the engine's own output. Never write a reason by hand.
- **Game lines come from FanDuel**, not DraftKings (the NHL's partner feed for Canada). No prop prices are connected yet.
- **Cashed slips tab.** Winning NHL slips are shown on a "Cashed slips" tab, under the same terms as the NBA one: winning slips only, the page says losing slips are not shown, no count of slips issued or lost. A slip made after puck drop is never shown. The full record stays private.
- **Preview runs.** Before goalies and lines are confirmed, `slate --preview` shows the board with the goalie and lines gates noted but not enforced. A preview is labelled as one and is never logged or graded.
- **Early card (owner, 24 November).** `slate --early` issues the card before confirmations when the owner asks for picks ahead of time: gates noted, slips logged and graded, labelled "early". Each later gated run re-issues a game's slips once its gates pass; a game whose gates never pass keeps its early slips.
- All thresholds live in `model/nhl/config.yaml`.
- If a data source cannot supply something the spec asks for, say so. Do not substitute silently.

## NBA module: standing rules

These rules apply to every session that touches the NBA player-prop module. The module is being built separately first and will be added to Godseye alongside the existing NFL algo.

### Goal

Project full probability distributions for NBA player props and build bet365 same-game parlays (SGPs) from them.

### Markets

- **Player:** points, rebounds, assists, 3-pointers made, steals, blocks, Points+Rebounds+Assists, Points+Rebounds, Points+Assists, double-double, triple-double.
- **Game:** moneyline, spread, alternative spread, game total, alternative total.

### Standing rules (carried over from the NFL algo)

1. **Algo only.** Picks come from this system's own output. No expert, media or consensus picks. Web lookups are allowed only for official injury reports, confirmed starters and rosters.
2. **No verified availability, no leg.** A player without a confirmed status for tonight cannot appear on a ticket.
3. **Floor rungs for SGPs.** Every SGP leg must have model probability of 70% or higher. Edge rungs (lower probability, positive expected value) are for straight singles only.
4. **Ticket structure per game:** one 4-leg and one 6-leg props-only SGP. Players from both teams are eligible; take the best legs regardless of side. Double-double and triple-double legs go on their own ticket and are never mixed into the props SGPs.
5. **Book format.** Support both bet365 over/under lines and bet365 milestone ladders (for example 20+, 25+, 30+ points). Only use rungs the book actually offers, read from the odds feed or a pasted CSV. Never assume a rung exists.
6. **Game script first.** No player prop is projected until the game-level simulation has run for that game. Blowout risk is assessed before any leg is considered.
7. **Point-in-time discipline.** Every feature uses only information available before tip-off. No leakage from the game being predicted.
8. **Shrink small samples.** Any split (home/away, versus a defender, last 5 games) is blended toward the player's baseline in proportion to sample size, and the sample size is shown next to the number.
9. **Log everything with a timestamp:** projection, probability, price taken, closing line, result.
10. **Explain every number.** Each projection carries an itemised list of the adjustments that moved it from baseline.

### Engineering rules

- Mirror the folder layout, naming and test style of the existing NFL module.
- Python for all modelling code.
- All thresholds (70% floor, blowout cutoffs, shrinkage strengths, caps) live in one config file. Nothing hard-coded.
- Write tests for every module. Do not change or break NFL code.
- If a data source cannot supply something a prompt asks for, stop and tell the user. Do not invent a substitute silently.

### Amendments (11 November 2026, from the owner)

- **Ticket sizes:** 4-leg, 6-leg and 8-leg props SGPs per game (rule 4 said 4 and 6).
- **Props tickets use four markets:** points, rebounds, assists, 3-pointers made. The other markets stay modelled but are not used on props tickets.
- **Multi-game slips:** 4 or 5 legs from each of 3 games (12 or 15 props), chosen by the algorithm's own joint probabilities. Every leg still needs 70%.
- **Book:** bet365 or DraftKings. DraftKings milestone ladders are read from ESPN's odds API. Rule 5 still holds: only rungs the book lists, and a rung is used only when it fits the player's over/under line.
- **Site:** landing page at `/`, NFL at `/nfl`, NBA at `/nba`.

### Amendments (19 November 2026)

- **4-leg slips use four different players.** 6-leg and 8-leg slips may still carry two legs on one player.
- **Rebound legs need 75%.** Every other market keeps the 70% floor.
- **Calibration from graded slates.** Each market's probabilities are shifted by what graded legs show, shrunk by sample size and capped (`model/nba/calibrate.py`). The ledger keeps the raw probability beside the calibrated one. All three settings live in `model/nba/config.py`.

### Amendments (20 November 2026, from the owner)

- **Never post results on the site.** No graded slips, records, units or "what cashed" on GodsEye (site or artifact). Grading still runs and is logged; results are reported to the owner in chat or as a private file only. Config: `site_show_results` stays False.
- **The all-games slip is made on request only**, delivered as a PDF, and is not shown on the site.
- **Leg floor is 75% in every market** (rule 3 said 70%). Slip legs the model called 70 to 74% hit 71% over six graded nights.
- **Rebound legs:** at most one per slip, and none on a 4-leg slip.
- **Slips per game:** a 4-leg, a second 4-leg on four different players, and a 6-leg. The 8-leg is dropped.

### Amendments (24 November 2026, from the owner)

- **Cashed slips showcase.** Winning algorithm slips are listed on a "Cashed slips" tab (site and artifact), each with an example stake and what it would have returned. This is the one exception to "never post results": the full tracker stays private (`site_show_results` False). The page does not show the count of slips issued or lost (owner, 24 November); it states that it lists winning slips only, that losing slips are not shown, and that stakes are examples and not bets placed. Config: `site_show_cashed`, `cashed_long_price`, `cashed_stake_long`, `cashed_stake_short`.
- **Price-band slips, locks and lotto (owner, 24 November).** Each game also gets three 6-leg slips chosen by listed price: safe (+100 to +200), realistic (+201 to +300) and upside (+301 to +400), each the highest-chance combination in its band, every leg still at 75% or better. A band no combination can reach is left empty and said so. The game's highest-chance 4-leg slip is marked "Lock". The NBA home page lists the "locks of the evening" (slip-eligible legs priced −300 to +100) and a parlay built from them; the Multi-game tab also carries one lotto slip (each game's longest band slip joined). The lotto slip is shown on the site, which replaces the 20 November "all-games slip is PDF only" rule for this slip. Code: `model/nba/bands.py`; settings in `model/nba/config.py` (`price_band_slips`, `value_lock_price_range`, `value_parlay_legs`, `lotto_slip`).
