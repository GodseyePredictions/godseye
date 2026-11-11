/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { Logo } from "@/components/Logo";
import locks from "../../../model/output/locks.json";
import nba from "../../../model/nba/output/nba_site.json";

const pct = (p: number) => `${Math.round(p * 100)}%`;
/** The price at which a bet with this chance breaks even (American odds). */
function fair(p: number) {
  const d = 1 / p;
  return d >= 2 ? `+${Math.round((d - 1) * 100)}` : `−${Math.round(100 / (d - 1))}`;
}

const steps = [
  {
    n: "01",
    h: "It reads everything that is public",
    p: "Every play, every box score, every official injury report, the schedule, the weather and the market line. Each number is stamped with the time it became known, so a prediction only ever uses what was known before kick-off or tip-off.",
  },
  {
    n: "02",
    h: "It plays the game thousands of times",
    p: "Before any player number, the algorithm simulates the game itself: pace, score, margin, and who sits if it turns into a blowout. NBA games are played 10,000 times each.",
  },
  {
    n: "03",
    h: "It puts every player inside those games",
    p: "Minutes, touches, shots, catches and scores are handed out inside each simulated game, so a quarterback and his receiver rise and fall together the way they do on the field.",
  },
  {
    n: "04",
    h: "It counts, then it shows its work",
    p: "A leg's chance is how often it hit across the simulations. A parlay's chance is how often every leg hit in the same game. Each pick comes with that number, the fair price and the reasons behind it.",
  },
];

const script = [
  ["The problem", "A parlay looks simple. Four legs, each one likely. But four likely things together are not likely, and the book prices that gap better than you can in your head."],
  ["What God's Eye is", "God's Eye is an AI algorithm prediction tool. It does not follow experts, the media or the crowd. It builds its own number for every player and every game."],
  ["How", "It reads the data, plays each game thousands of times, and counts how often each bet wins. Then it builds the same-game parlays it likes best and tells you the true chance of the whole slip."],
  ["What you get", "Algorithm picks for the NFL and the NBA, a builder that prices your own slip leg by leg, and a tracker that shows where your money really goes."],
  ["The honest part", "It is a model, not a crystal ball. Every pick shows its chance of losing as clearly as its chance of winning, and we publish the record either way."],
];

const nflHow = [
  ["A chance for every player, every week", "For each skill player the algorithm estimates the chance of a touchdown and of clearing every yardage, reception and carry rung, from every play since 2021."],
  ["Sixteen factors, all from data", "Play-calling on both sides, the defenders he will actually face, injuries to both units, his route profile, weather, surface, travel, rest and kickoff slot, anchored to the market's implied team total."],
  ["Legs priced together", "Teammates split touchdowns and a quarterback rises with his receivers. Parlay chances use correlations measured on past games, so a ticket's number is the whole ticket's chance."],
  ["Graded as shipped", "Every week is graded on the picks as they were posted, with no swaps afterwards, and each graded week feeds a change to the algorithm."],
];
const nflExpect = [
  "Single floor legs (the 70 to 88% band) have hit 76 to 81% in testing: about four in five.",
  "A four-leg ticket of those legs cashes about four times in ten. Six legs, about one in four.",
  "Last graded week: 18 of 64 tickets cashed, with legs hitting 73% against 71% expected.",
  "Losing weeks are normal. The touchdown model is tested against two seasons it never saw; the game-line model does not beat the closing line, so its game parlays are fair-price references.",
];
const nflPlay = [
  ["Keep slips short", "Every added leg multiplies the chance down. The 4-leg tickets are the algorithm's strongest."],
  ["Stay on floor rungs", "Take the rung the model gives 70% or better, not the one with the bigger payout."],
  ["Beat the fair price", "Each ticket shows a fair price. If your book pays less than that, pass."],
  ["Respect singles only", "Questionable players and players just back from an absence are flagged singles only. Keep them off parlays."],
  ["Re-check before kickoff", "Inactives post about 90 minutes before kickoff and the picks are re-run. Bet after that, not before."],
  ["One touchdown scorer per team", "Teammates share a team's touchdowns. The algorithm never pairs them; neither should you."],
  ["Flat stakes, tracked", "Bet the same small amount each time and log every slip in the tracker so you can see what pays."],
];

type Star = {
  name: string;
  tag: string;
  status?: string;
  rows: { label: string; value: string; note?: string }[];
  photo: string | null;
};
const slug = (n: string) => n.toLowerCase().replace(/ /g, "-").replace(/[^a-z0-9-]/g, "");

function StarCard({ s }: { s: Star }) {
  const initials = s.name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <div className="star">
      {s.photo ? <img className="star-photo" src={s.photo} alt={s.name} /> : <div className="star-mono" aria-hidden="true">{initials}</div>}
      <div className="star-body">
        <h3>{s.name}</h3>
        <p className="star-tag">{s.tag}</p>
        {s.status && <p className="star-status">{s.status}</p>}
        <dl>
          {s.rows.map((r) => (
            <div key={r.label}>
              <dt>{r.label}</dt>
              <dd>
                <b className="num">{r.value}</b>
                {r.note && <small>{r.note}</small>}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}

const NBA_FEATURED = ["LeBron James", "Shai Gilgeous-Alexander", "Kawhi Leonard", "Stephen Curry"];

export default function Home() {
  const rec = locks.record;
  // The single-file preview carries the banner inline (window.GE_BANNER); the site serves it from /brand.
  const banner = (typeof window !== "undefined" && (window as { GE_BANNER?: string }).GE_BANNER) || "/brand/banner.jpg";
  const nbaTickets = nba.games.reduce((n, g) => n + g.tickets.length, 0);
  // Player photos are optional files in public/players (none ship with the repo); the preview carries them inline.
  const inlinePhotos = typeof window !== "undefined" ? (window as { GE_PHOTOS?: Record<string, string> }).GE_PHOTOS : undefined;
  const photo = (name: string) =>
    inlinePhotos?.[slug(name)] ?? ((locks.photos as string[]).includes(slug(name)) ? `/players/${slug(name)}.jpg` : null);
  const nflStars: Star[] = locks.stars.map((p) =>
    p.on_slate
      ? {
          name: p.name,
          tag: `${p.pos} · ${p.team} · ${p.game} · ${p.when}`,
          status: p.singles_only ? "Singles only this week" : undefined,
          rows: [
            ...(p.lines ?? []).map((l) => ({ label: l.text, value: pct(l.p), note: l.record })),
            { label: "Anytime touchdown", value: pct(p.atd ?? 0) },
          ],
          photo: photo(p.name),
        }
      : { name: p.name, tag: "Not on this week's slate", rows: [], photo: photo(p.name) },
  );
  type NbaPlayer = { name: string; team: string; status: string; min_mean: number; pts: number; reb: number; ast: number; fg3m: number };
  const nbaStars: Star[] = NBA_FEATURED.map((name) => {
    for (const g of nba.games as unknown as { home: string; away: string; players: NbaPlayer[]; availability: { name: string; status: string; reason: string | null }[] }[]) {
      const p = g.players.find((x) => x.name === name);
      if (p)
        return {
          name,
          tag: `${p.team} · ${g.away} @ ${g.home} · tonight`,
          status: p.status === "confirmed_in" ? undefined : `Listed ${p.status}`,
          rows: [
            { label: "Points", value: p.pts.toFixed(1) },
            { label: "Rebounds", value: p.reb.toFixed(1) },
            { label: "Assists", value: p.ast.toFixed(1) },
            { label: "Threes", value: p.fg3m.toFixed(1) },
            { label: "Minutes", value: p.min_mean.toFixed(0) },
          ],
          photo: photo(name),
        };
      const a = g.availability.find((x) => x.name === name);
      if (a) return { name, tag: `${g.away} @ ${g.home} · tonight`, status: `${a.status.toUpperCase()}: ${a.reason ?? "no reason given"}`, rows: [], photo: photo(name) };
    }
    return { name, tag: "His team does not play tonight", rows: [], photo: photo(name) };
  });
  return (
    <>
      <header className="wrap top">
        <Logo />
        <nav aria-label="Main">
          <a href="#how" className="hide-sm">
            How it works
          </a>
          <a href="#locks" className="hide-sm">
            Locks of the week
          </a>
          <a href="#nfl" className="hide-sm">
            NFL explained
          </a>
          <Link href="/nfl" className="tab-link">
            NFL
          </Link>
          <Link href="/nba" className="tab-link">
            NBA
          </Link>
        </nav>
      </header>

      <main>
        <section className="eye-hero">
          <img className="eye-banner" src={banner} alt="" width={1206} height={214} />
          <div className="wrap eye-copy">
            <p className="kicker">AI algorithm predictions · NFL and NBA</p>
            <h1 className="display">
              The eye sees <em>the whole slip</em>
            </h1>
            <p className="lede">
              God&apos;s Eye is an AI algorithm prediction tool. It simulates every game thousands of times, prices every player prop, and
              builds same-game parlays with the true chance of the whole ticket on the front.
            </p>
            <div className="actions">
              <Link href="/nfl" className="btn btn-primary">
                Open NFL
              </Link>
              <Link href="/nba" className="btn btn-ghost">
                Open NBA
              </Link>
              <a href="#locks" className="btn btn-ghost">
                Locks of the week
              </a>
            </div>
          </div>
        </section>

        <section id="how" className="band band-deep">
          <div className="wrap">
            <h2 className="display">How it works</h2>
            <p className="intro">
              No experts. No media picks. No consensus. One algorithm that builds its own number for every leg and shows you how it got
              there.
            </p>
            <div className="steps">
              {steps.map((s) => (
                <div key={s.n}>
                  <span className="step-n">{s.n}</span>
                  <h3>{s.h}</h3>
                  <p>{s.p}</p>
                </div>
              ))}
            </div>

            <div className="script">
              <h3>The 60-second version</h3>
              <dl>
                {script.map(([a, b]) => (
                  <div key={a}>
                    <dt>{a}</dt>
                    <dd>{b}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        <section id="locks" className="band">
          <div className="wrap">
            <h2 className="display">Locks of the week</h2>
            <p className="intro">
              NFL week {locks.week}. These are the algorithm&apos;s own top tickets: its three highest-probability same-game parlays, its best
              touchdown double and its 4-leg touchdown ticket. Nothing here was hand-picked.
            </p>
            <div className="locks">
              {locks.locks.map((t) => (
                <div className="slip lock" key={t.kind + t.matchup}>
                  <div className="slip-head">
                    <span>{t.kind}</span>
                    <small>
                      {t.matchup} · {t.when}
                    </small>
                  </div>
                  {t.legs.map((l) => (
                    <div className="leg" key={l.text}>
                      <div className="leg-row">
                        <span>{l.text}</span>
                        <span className="num">{pct(l.p)}</span>
                      </div>
                      <div className="leg-sub">
                        {l.team}
                        {"record" in l && l.record ? ` · ${l.record}` : ""}
                      </div>
                    </div>
                  ))}
                  <div className="slip-foot">
                    <span>
                      Model chance <b>{pct(t.p)}</b>
                    </span>
                    <span className="num">fair {fair(t.p)}</span>
                  </div>
                  <Link href={`/nfl#${t.tab}`} className="lock-link">
                    See the reasons in the NFL console
                  </Link>
                </div>
              ))}
            </div>
            <p className="backing">
              <strong>We back them with the record, win or lose.</strong> In the last graded week {rec.cashed} of the algorithm&apos;s{" "}
              {rec.tickets} tickets cashed, and {rec.legs_hit}% of its legs hit against {rec.legs_exp}% expected. A parlay at{" "}
              {pct(locks.locks[0]?.p ?? 0)} still loses more often than it wins: take a price better than the fair price shown, or pass.
            </p>
          </div>
        </section>

        <section id="nfl" className="band band-deep">
          <div className="wrap">
            <p className="kicker">NFL · week {locks.week}</p>
            <h2 className="display">How the NFL algorithm works</h2>
            <div className="stars">
              {nflStars.map((s) => (
                <StarCard s={s} key={s.name} />
              ))}
            </div>
            <p className="star-note">The algorithm&apos;s own numbers for this week. The percentage is its chance the player clears that mark.</p>
            <div className="steps">
              {nflHow.map(([h, p]) => (
                <div key={h}>
                  <h3>{h}</h3>
                  <p>{p}</p>
                </div>
              ))}
            </div>
            <div className="two">
              <div>
                <h3 className="sub-h">What to expect</h3>
                <ul className="plain">
                  {nflExpect.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="sub-h">How to play it for a better hit rate</h3>
                <ul className="plain">
                  {nflPlay.map(([h, p]) => (
                    <li key={h}>
                      <strong>{h}.</strong> {p}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <Link href="/nfl" className="btn btn-primary">
              Open the NFL picks
            </Link>
          </div>
        </section>

        <section id="nba" className="band">
          <div className="wrap">
            <p className="kicker">NBA · tonight</p>
            <h2 className="display">The NBA side</h2>
            <p className="intro">
              Every game is played 10,000 times before a single player number is produced. Each player&apos;s points, rebounds, assists
              and threes are then counted inside those same games, and priced against DraftKings&apos; ladders.
            </p>
            <div className="stars">
              {nbaStars.map((s) => (
                <StarCard s={s} key={s.name} />
              ))}
            </div>
            <p className="star-note">Tonight&apos;s projected averages if the player takes the floor. Availability is from the official NBA injury report.</p>
            <Link href="/nba" className="btn btn-primary">
              Open the NBA picks
            </Link>
          </div>
        </section>

        <section id="sports" className="band band-deep">
          <div className="wrap">
            <h2 className="display">Pick your sport</h2>
            <div className="sport-cards">
              <Link href="/nfl" className="sport-card">
                <span className="sport-tag">NFL</span>
                <h3>Week {locks.week} is live</h3>
                <ul>
                  <li>Algorithm picks and anytime-touchdown board</li>
                  <li>A same-game parlay for every game</li>
                  <li>Game parlays, hybrid SGPs and game scripts</li>
                  <li>Build, audit and track your own slips</li>
                </ul>
                <span className="btn btn-primary">Open NFL</span>
              </Link>
              <Link href="/nba" className="sport-card">
                <span className="sport-tag">NBA</span>
                <h3>
                  {nba.games.length} games, {nbaTickets} tickets tonight
                </h3>
                <ul>
                  <li>4-leg, 6-leg and 8-leg props SGPs for every game</li>
                  <li>Game script card: pace, margin, blowout risk</li>
                  <li>Projection board with the reasons for every number</li>
                  <li>Availability from the official injury report</li>
                </ul>
                <span className="btn btn-primary">Open NBA</span>
              </Link>
            </div>
          </div>
        </section>

        <section className="band">
          <div className="wrap">
            <h2 className="display">Straight talk</h2>
            <div className="straight">
              <p>
                <strong>God&apos;s Eye is not a sportsbook.</strong> You cannot place a bet here. You place bets with your own book and
                bring the slip to us.
              </p>
              <p>
                <strong>&quot;Lock&quot; is a name, not a guarantee.</strong> Every ticket shows its real chance. Sportsbooks price in an
                edge and most bettors lose over time.
              </p>
              <p>
                <strong>The NBA side is new.</strong> It prices against DraftKings ladders and flags a ticket when the model sees
                negative value. Its test measured how often legs hit, not profit.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="wrap">
          <p>
            For adults of legal betting age in their province (18+ or 19+). God&apos;s Eye provides information and analysis, not betting
            advice you should rely on for financial decisions.
          </p>
          <p>
            If gambling is causing you harm, free and confidential help is available in every province. Set a budget and never bet money
            you cannot afford to lose.
          </p>
        </div>
      </footer>
    </>
  );
}
