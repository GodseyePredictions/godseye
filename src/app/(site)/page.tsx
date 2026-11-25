/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { SiteFooter } from "@/components/InfoPages";
import { Logo } from "@/components/Logo";
import locksJson from "../../../model/output/locks.json";
import nba from "../../../model/nba/output/nba_site.json";
import nhl from "../../../model/nhl/output/nhl_site.json";
import { Slip, american, pct as pc } from "@/components/Slip";
import { nbaPicks } from "@/lib/advisor/picks";
import { nbaWhy } from "@/lib/lock-intel";
import { picksOfTheDay } from "@/lib/picks-of-day";
import { ADVISOR_LIMITS } from "@/lib/advisor/subscription";

/* The shape of model/output/locks.json (scripts/build-locks.py). Written out here so the page still builds
   in a week when a list is empty, for example a rebuild after every game has kicked off. */
type LockLeg = { text: string; team: string; p: number; record?: string; why?: string[] };
type Lock = { kind: string; matchup: string; when: string; p: number; tab: string; legs: LockLeg[]; intel?: string[] };
type NflStar = {
  name: string;
  on_slate: boolean;
  team?: string;
  pos?: string;
  game?: string;
  when?: string;
  atd?: number;
  singles_only?: boolean;
  lines?: { text: string; p: number; record?: string }[];
};
const locks = locksJson as unknown as { stars: NflStar[]; photos: string[]; season: number; week: number; built: string; locks: Lock[] };

const pct = (p: number) => `${Math.round(p * 100)}%`;

/* Tonight's NBA board for the landing page, straight from the NBA algorithm's output: per game the Lock (its
   highest-chance 4-leg slip) and the price-band 6-leg slips, then the multi-game slips with the lotto ticket last. */
type NbaSiteLeg = { label: string; p: number };
type NbaSiteTicket = { type: string; joint: number; book_price: number | null; legs: NbaSiteLeg[] };
type NbaSiteMulti = { type: string; n_legs: number; joint: number; book_price: number | null; parts: { matchup: string; legs: NbaSiteLeg[] }[] };
const NBA_BANDS: [string, string][] = [
  ["band_safe6", "Safe 6-leg"],
  ["band_real6", "Realistic 6-leg"],
  ["band_up6", "Upside 6-leg"],
];
const NBA_MULTI_TITLE: Record<string, string> = { value_locks: "Locks parlay", lotto: "Lotto ticket" };
function nbaBoardOf(site: unknown) {
  const S = site as { games: { home: string; away: string; preview?: boolean; tickets: NbaSiteTicket[] }[]; multi?: NbaSiteMulti[] };
  const games = S.games
    .filter((g) => !g.preview)
    .map((g) => {
      const fours = g.tickets.filter((t) => t.type === "props_4" || t.type === "props_4b");
      const lock = fours.length ? fours.reduce((a, b) => (b.joint > a.joint ? b : a)) : null;
      const bands = NBA_BANDS.flatMap(([k, name]) => g.tickets.filter((t) => t.type === k).map((t) => ({ ...t, meta: name })));
      return { game: `${g.away} @ ${g.home}`, slips: [...(lock ? [{ ...lock, meta: "Lock" }] : []), ...bands] };
    })
    .filter((g) => g.slips.length > 0);
  const multi = [...(S.multi ?? [])]
    .sort((a, b) => Number(a.type === "lotto") - Number(b.type === "lotto"))
    .map((m) => ({ ...m, title: NBA_MULTI_TITLE[m.type] ?? `${m.n_legs} props, ${m.parts.length} games` }));
  return { games, multi };
}
const nbaBoard = nbaBoardOf(nba);
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
  ["The honest part", "It is a model, not a crystal ball. Every pick shows its chance of losing as clearly as its chance of winning."],
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

/* Player card art: the player's initials on his team's colours, with a football or basketball mark.
   It is graphic design, not a photograph, and carries no league or team marks.
   A licensed photo placed in public/players replaces it for that player. */
type Pose = "throw" | "run" | "catch" | "shot" | "dunk" | "drive" | "defend";
const TEAM_COLOURS: Record<string, [string, string]> = {
  KC: ["#c8102e", "#ffb81c"], BUF: ["#00338d", "#c60c30"], CIN: ["#fb4f14", "#ffffff"], PHI: ["#006bb6", "#ed174c"],
  OKC: ["#007ac1", "#ef3b24"], TOR: ["#ce1141", "#c4ced4"], GS: ["#1d428a", "#ffc72c"], LAL: ["#552583", "#fdb927"],
};
function PlayerArt({ name, pose, team }: { name: string; pose: Pose; team?: string }) {
  const hoops = ["shot", "dunk", "drive", "defend"].includes(pose);
  const [c1, c2] = TEAM_COLOURS[team ?? ""] ?? ["#d6192b", "#d9a53a"];
  const id = slug(name);
  const initials = name.split(" ").map((w) => w[0]).slice(0, 2).join("");
  return (
    <svg className="star-art" viewBox="0 0 200 150" role="img" aria-label={`Illustration for ${name}`} preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={`g-${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={c1} />
          <stop offset="0.62" stopColor="#120d10" />
          <stop offset="1" stopColor="#0a090b" />
        </linearGradient>
        <radialGradient id={`s-${id}`} cx="0.5" cy="0.25" r="0.6">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.28" />
          <stop offset="1" stopColor="#ffffff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="200" height="150" fill={`url(#g-${id})`} />
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <line key={i} x1={-40 + i * 34} y1="150" x2={30 + i * 34} y2="0" stroke={c2} strokeOpacity={0.1 + (i % 3) * 0.05} strokeWidth={i % 2 ? 3 : 9} />
      ))}
      <rect width="200" height="150" fill={`url(#s-${id})`} />
      <text x="100" y="104" textAnchor="middle" className="star-art-ini" fill="#ffffff">
        {initials}
      </text>
      <rect x="62" y="116" width="76" height="5" fill={c2} transform="skewX(-14)" />
      {hoops ? (
        <g transform="translate(170 26)" fill="none" stroke="#ffffff" strokeOpacity="0.85" strokeWidth="1.6">
          <circle r="12" fill={c2} fillOpacity="0.9" />
          <path d="M-12 0H12M0 -12V12M-8.5 -8.5C-3 -3 -3 3 -8.5 8.5M8.5 -8.5C3 -3 3 3 8.5 8.5" />
        </g>
      ) : (
        <g transform="translate(170 26) rotate(-28)" fill="none" stroke="#ffffff" strokeOpacity="0.85" strokeWidth="1.6">
          <ellipse rx="15" ry="9" fill={c2} fillOpacity="0.9" />
          <path d="M-7 0H7M-4 -3V3M0 -3V3M4 -3V3" />
        </g>
      )}
      <rect x="0" y="146" width="200" height="4" fill={c2} />
      {team && (
        <text x="10" y="20" className="star-art-team" fill="#ffffff">
          {team}
        </text>
      )}
    </svg>
  );
}

type Star = {
  name: string;
  pose: Pose;
  team?: string;
  tag: string;
  status?: string;
  rows: { label: string; value: string; note?: string }[];
  photo: string | null;
};
const slug = (n: string) => n.toLowerCase().replace(/ /g, "-").replace(/[^a-z0-9-]/g, "");

function StarCard({ s }: { s: Star }) {
  return (
    <div className="star">
      {s.photo ? <img className="star-photo" src={s.photo} alt={s.name} /> : <PlayerArt name={s.name} pose={s.pose} team={s.team} />}
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

const NFL_ART: Record<string, { pose: Pose }> = {
  "Patrick Mahomes": { pose: "throw" },
  "Josh Allen": { pose: "throw" },
  "Ja'Marr Chase": { pose: "catch" },
  "Kenneth Walker III": { pose: "run" },
};
const NBA_ART: Record<string, { pose: Pose; team?: string }> = {
  "LeBron James": { pose: "dunk" },
  "Shai Gilgeous-Alexander": { pose: "drive" },
  "Kawhi Leonard": { pose: "defend", team: "TOR" },
  "Stephen Curry": { pose: "shot" },
};
const NBA_FEATURED = Object.keys(NBA_ART);

export default function Home() {
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
          ...NFL_ART[p.name],
          team: p.team,
          tag: `${p.pos} · ${p.team} · ${p.game} · ${p.when}`,
          status: p.singles_only ? "Singles only this week" : undefined,
          rows: [
            ...(p.lines ?? []).map((l) => ({ label: l.text, value: pct(l.p), note: l.record })),
            { label: "Anytime touchdown", value: pct(p.atd ?? 0) },
          ],
          photo: photo(p.name),
        }
      : { name: p.name, ...NFL_ART[p.name], tag: "Not on this week's slate", rows: [], photo: photo(p.name) },
  );
  type NbaPlayer = { name: string; team: string; status: string; min_mean: number; pts: number; reb: number; ast: number; fg3m: number };
  const nbaStars: Star[] = NBA_FEATURED.map((name) => {
    for (const g of nba.games as unknown as { home: string; away: string; players: NbaPlayer[]; availability: { name: string; status: string; reason: string | null }[] }[]) {
      const p = g.players.find((x) => x.name === name);
      if (p)
        return {
          name,
          ...NBA_ART[name],
          team: p.team,
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
      if (a) return { name, ...NBA_ART[name], tag: `${g.away} @ ${g.home} · tonight`, status: `${a.status.toUpperCase()}: ${a.reason ?? "no reason given"}`, rows: [], photo: photo(name) };
    }
    return { name, ...NBA_ART[name], tag: "His team does not play tonight", rows: [], photo: photo(name) };
  });
  const day = picksOfTheDay(nbaPicks(nba));
  const dayLabel = day.date ? new Date(`${day.date}T12:00:00Z`).toLocaleDateString("en-CA", { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" }) : null;
  const heroSlips = day.best.length ? day.best : [];
  const nbaReasons = (p: { game: string; legs: { leg: string }[] }) => {
    const w = nbaWhy(nba, p.game);
    return w ? { intel: w.intel, legs: p.legs.map((l) => ({ text: l.leg, why: w.legs[l.leg] ?? [] })) } : undefined;
  };
  const marquee = ["See the whole slip", "Algorithm picks only", "Bet smarter, survive the variance", "Every slip shows its chance of losing"];

  return (
    <div className="lp">
      <a className="lp-skip" href="#content">
        Skip to content
      </a>
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-in">
          <Logo />
          <nav aria-label="Main">
            <a href="#picks">Algo Locks</a>
            <a href="#how">How it works</a>
            <a href="#tools">What you get</a>
            <a href="#mission">Mission</a>
            <a href="#faq">Questions</a>
          </nav>
          <div className="lp-sports" role="group" aria-label="Choose a sport">
            <Link href="/nfl">NFL</Link>
            <Link href="/nba">NBA</Link>
            <Link href="/nhl">NHL</Link>
          </div>
        </div>
      </header>

      <main id="content">
        {/* ---- hero: the product itself, a real algorithm slip ---- */}
        <section className="lp-hero">
          <img className="lp-hero-eye" src={banner} alt="" width={1206} height={214} />
          <div className="lp-wrap lp-hero-in">
            <div className="lp-hero-copy">
              <h1>See the whole slip before you bet it.</h1>
              <p>
                Godseye plays every game thousands of times, prices every player prop, and prints the true chance of the whole ticket on the
                front. No experts. No media picks. One algorithm, and it shows its work.
              </p>
              <div className="lp-cta">
                <Link href="/nfl" className="lp-btn lp-btn-red">
                  Open NFL
                </Link>
                <Link href="/nba" className="lp-btn lp-btn-white">
                  Open NBA
                </Link>
                <a href="#picks" className="lp-btn lp-btn-line">
                  Algo Locks
                </a>
              </div>
              <p className="lp-hero-small">Not a sportsbook. You place bets with your own book and bring the slip here.</p>
            </div>
            <div className="lp-fan" aria-label="Slips from the algorithm">
              {heroSlips.length ? (
                heroSlips.slice(0, 3).map((p, i) => (
                  <div className={`lp-fan-card f${i}`} key={p.game + p.kind}>
                    <Slip
                      title={p.game}
                      meta="NBA"
                      legs={p.legs.slice(0, 4).map((l) => ({ text: l.leg, value: pc(l.probability) }))}
                      stats={[{ label: "Chance to hit", value: pc(p.joint_probability, 1), tone: "red" }, { label: "Legs", value: String(p.legs.length) }]}
                    />
                  </div>
                ))
              ) : (
                <div className="lp-fan-card f0">
                  <Slip title="Tonight's slate" meta="NBA" note="The next slips print here when the algorithm builds the slate." />
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ---- the scrolling logo band ---- */}
        <div className="lp-marquee" aria-hidden="true">
          <div className="lp-marquee-track">
            {[0, 1].map((copy) => (
              <div className="lp-marquee-set" key={copy}>
                {marquee.map((t) => (
                  <span className="lp-marquee-item" key={t}>
                    <Logo href="#content" />
                    <b>{t}</b>
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* ---- sport switch ---- */}
        <section className="lp-band" id="sports">
          <div className="lp-wrap">
            <div className="lp-switch">
              <Link href="/nfl" className="lp-sport nfl">
                <span className="lp-sport-name">NFL</span>
                <span className="lp-sport-line">{locks.locks.length ? `Week ${locks.week}: ${locks.locks.length} algorithm tickets open` : `Week ${locks.week} has kicked off. The next week prints on Tuesday.`}</span>
                <ul>
                  <li>Algorithm picks and the anytime-touchdown board</li>
                  <li>A same-game parlay for every game</li>
                  <li>Game scripts, weather and matchup reads</li>
                </ul>
                <span className="lp-sport-go">Go to NFL</span>
              </Link>
              <Link href="/nba" className="lp-sport nba">
                <span className="lp-sport-name">NBA</span>
                <span className="lp-sport-line">
                  {nba.games.length} games and {nbaTickets} slips on the board
                </span>
                <ul>
                  <li>Props same-game parlays for every game</li>
                  <li>Pace, margin and blowout risk before any prop</li>
                  <li>Only players confirmed available make a slip</li>
                </ul>
                <span className="lp-sport-go">Go to NBA</span>
              </Link>
              <Link href="/nhl" className="lp-sport nba">
                <span className="lp-sport-name">NHL</span>
                <span className="lp-sport-line">
                  {nhl.games.length} {nhl.games.length === 1 ? "game" : "games"} and {nhl.games.reduce((n, g) => n + g.tickets.length, 0) + nhl.multi.length} {nhl.preview ? "preview" : "test"} slips on the board
                </span>
                <ul>
                  <li>Every game simulated 20,000 times before any prop</li>
                  <li>Shots, hits, blocks, points and saves from the same games</li>
                  <li>No confirmed goalie, no scoring leg</li>
                </ul>
                <span className="lp-sport-go">Go to NHL</span>
              </Link>
            </div>
          </div>
        </section>

        {/* ---- picks of the day ---- */}
        <section className="lp-band lp-band-deep" id="picks">
          <div className="lp-wrap">
            <h2>Algo Locks</h2>
            <p className="lp-intro">
              The slips the algorithm gives the best chance of hitting, ranked by its own number, with its reasoning under each one. Nobody
              picked them by hand. &ldquo;Lock&rdquo; is our name for the algorithm&apos;s strongest slips, not a promise: each one shows how
              often it misses.
            </p>
            <h3 className="lp-sub">{dayLabel ? `NBA, ${dayLabel}` : "NBA"}</h3>
            {day.best.length ? (
              <>
                <div className="gs-slips lp-day">
                  {day.best.map((p, i) => (
                    <Slip
                      key={p.game + p.kind}
                      title={p.game}
                      meta={i === 0 ? "Game of the day" : p.kind}
                      legs={p.legs.map((l) => ({ text: l.leg, value: pc(l.probability) }))}
                      why={nbaReasons(p)}
                      stats={[
                        { label: "Chance to hit", value: pc(p.joint_probability, 1), tone: "red" },
                        { label: "Chance to miss", value: pc(1 - (p.joint_probability as number), 1) },
                        ...(p.book_price != null ? [{ label: p.price_is_estimate ? "Legs multiplied" : "Book odds", value: american(p.book_price) }] : []),
                      ]}
                    />
                  ))}
                </div>
                {day.topPerGame.length > day.best.length && (
                  <>
                    <h3 className="lp-sub">Top slip for every other game</h3>
                    <div className="gs-slips">
                      {day.topPerGame.slice(day.best.length).map((p) => (
                        <Slip
                          key={p.game + p.kind}
                          title={p.game}
                          meta={p.kind}
                          legs={p.legs.map((l) => ({ text: l.leg, value: pc(l.probability) }))}
                          why={nbaReasons(p)}
                          stats={[
                            { label: "Chance to hit", value: pc(p.joint_probability, 1), tone: "red" },
                            { label: "Chance to miss", value: pc(1 - (p.joint_probability as number), 1) },
                          ]}
                        />
                      ))}
                    </div>
                  </>
                )}
              </>
            ) : (
              <p className="lp-empty">No slips are on the board right now. They print here as soon as the algorithm builds the next slate.</p>
            )}
            {nbaBoard.games.length > 0 && (
              <>
                <h3 className="lp-sub" id="nba-slips">
                  NBA: every game, by price
                </h3>
                <p className="lp-intro">
                  For each game: the Lock (the algorithm&apos;s highest-chance 4-leg slip), then three 6-leg slips chosen by price. Safe pays
                  +100 to +200, realistic +201 to +300, upside +301 to +400. Every leg is rated 75% or better. Prices are the book&apos;s
                  leg prices multiplied together; a real same-game price pays less.
                </p>
                {nbaBoard.games.map((g) => (
                  <div key={g.game}>
                    <h3 className="lp-sub">{g.game}</h3>
                    <div className="gs-slips">
                      {g.slips.map((t) => (
                        <Slip
                          key={g.game + t.meta}
                          title={g.game}
                          meta={t.meta}
                          legs={t.legs.map((l) => ({ text: l.label, value: pc(l.p) }))}
                          stats={[
                            { label: "Chance to hit", value: pc(t.joint, 1), tone: "red" },
                            { label: "Chance to miss", value: pc(1 - t.joint, 1) },
                            ...(t.book_price != null ? [{ label: "Legs multiplied", value: american(t.book_price) }] : []),
                          ]}
                        />
                      ))}
                    </div>
                  </div>
                ))}
                {nbaBoard.multi.length > 0 && (
                  <>
                    <h3 className="lp-sub" id="nba-multi-slips">
                      NBA: multi-game slips and the lotto ticket
                    </h3>
                    <p className="lp-intro">
                      Slips that join legs from several games. The lotto ticket is a long shot by design: every leg has to hit, and it
                      loses far more often than it wins. Stake it small.
                    </p>
                    <div className="gs-slips">
                      {nbaBoard.multi.map((m) => (
                        <Slip
                          key={m.title}
                          title={m.title}
                          meta={`${m.n_legs} legs`}
                          legs={m.parts.flatMap((p) => p.legs.map((l) => ({ text: l.label, sub: p.matchup, value: pc(l.p) })))}
                          stats={[
                            { label: "Chance to hit", value: pc(m.joint, 1), tone: "red" },
                            { label: "Chance to miss", value: pc(1 - m.joint, 1) },
                            ...(m.book_price != null ? [{ label: "Legs multiplied", value: american(m.book_price) }] : []),
                          ]}
                        />
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
            {locks.locks.length > 0 && (
              <>
                <h3 className="lp-sub">NFL, week {locks.week}</h3>
                <div className="gs-slips">
                  {locks.locks.map((t) => (
                    <Slip
                      key={t.kind + t.matchup}
                      title={t.matchup}
                      meta={t.kind}
                      legs={t.legs.map((l) => ({ text: l.text, sub: l.record || undefined, value: pct(l.p) }))}
                      why={{ intel: t.intel, legs: t.legs.map((l) => ({ text: l.text, why: l.why ?? [] })) }}
                      stats={[
                        { label: "Chance to hit", value: pct(t.p), tone: "red" },
                        { label: "Chance to miss", value: pct(1 - t.p) },
                        { label: "Fair odds", value: fair(t.p) },
                      ]}
                    />
                  ))}
                </div>
              </>
            )}
            <p className="lp-fine">
              Every slip shows its chance of losing. A parlay loses more often than it wins: take a price better than fair, or pass.
            </p>
            <div className="lp-cta">
              <Link href="/nba" className="lp-btn lp-btn-red">
                All NBA slips
              </Link>
              <Link href="/nfl" className="lp-btn lp-btn-line">
                All NFL picks
              </Link>
            </div>
          </div>
        </section>

        {/* ---- how it works: a real sequence, so it is numbered ---- */}
        <section className="lp-band" id="how">
          <div className="lp-wrap">
            <h2>How it works</h2>
            <ol className="lp-steps">
              {steps.map((st) => (
                <li key={st.h}>
                  <h3>{st.h}</h3>
                  <p>{st.p}</p>
                </li>
              ))}
            </ol>
            <dl className="lp-story">
              {script.map(([h, t]) => (
                <div key={h}>
                  <dt>{h}</dt>
                  <dd>{t}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ---- what you get ---- */}
        <section className="lp-band lp-band-deep" id="tools">
          <div className="lp-wrap">
            <h2>What you get</h2>
            <div className="lp-tools">
              <Link href="/nfl#picks" className="lp-tool">
                <h3>Algorithm picks</h3>
                <p>Slips for every game with the chance of the whole ticket on the front and the reason behind every leg.</p>
                <span>See the picks</span>
              </Link>
              <Link href="/nfl#shot" className="lp-tool">
                <h3>Slip audit</h3>
                <p>Upload a screenshot of your own slip. Each leg is rated or marked unrated, and you get a better version built from the algorithm.</p>
                <span>Audit a slip</span>
              </Link>
              <Link href="/nfl#bankroll" className="lp-tool">
                <h3>Bankroll Strategy</h3>
                <p>Stakes in units and dollars, sized from the algorithm&apos;s chance and held inside the limits you set: stop-loss, nightly cap, cool-off.</p>
                <span>Set your bankroll</span>
              </Link>
              <Link href="/nfl#advisor" className="lp-tool">
                <h3>Your advisor</h3>
                <p>A one-to-one chat that knows your slips and your bankroll. Every number it quotes comes from the algorithm, never a hunch.</p>
                <span>Ask your advisor</span>
              </Link>
            </div>
          </div>
        </section>

        {/* ---- goal and mission ---- */}
        <section className="lp-band lp-mission" id="mission">
          <div className="lp-wrap lp-mission-in">
            <div>
              <h2>Our goal</h2>
              <p className="lp-statement">Every bettor sees the true chance of a slip before the book takes it.</p>
            </div>
            <div>
              <h2>Our mission</h2>
              <p className="lp-statement">
                Replace hunches, hot takes and parlays built on hope with numbers anyone can check, and give bettors what it takes to stay in the
                game: honest odds, disciplined stakes and limits they set themselves.
              </p>
            </div>
            <ul className="lp-taglines">
              <li>See the whole slip.</li>
              <li>Bet smarter, survive the variance.</li>
              <li>One algorithm. No opinions.</li>
            </ul>
          </div>
        </section>

        {/* ---- the names you know, with the algorithm's numbers ---- */}
        <section className="lp-band lp-band-deep" id="players">
          <div className="lp-wrap">
            <h2>The algorithm&apos;s numbers on the names you know</h2>
            <h3 className="lp-sub">NFL, week {locks.week}</h3>
            <div className="stars">
              {nflStars.map((s) => (
                <StarCard s={s} key={s.name} />
              ))}
            </div>
            <h3 className="lp-sub">NBA</h3>
            <div className="stars">
              {nbaStars.map((s) => (
                <StarCard s={s} key={s.name} />
              ))}
            </div>
            <p className="lp-fine">NFL: the chance the player clears that mark. NBA: projected averages if he takes the floor, with availability from the official injury report.</p>
          </div>
        </section>

        {/* ---- the NFL guide ---- */}
        <section className="lp-band" id="nfl-guide">
          <div className="lp-wrap">
            <h2>How the NFL algorithm works</h2>
            <div className="lp-tools lp-guide">
              {nflHow.map(([h, t]) => (
                <div className="lp-tool" key={h}>
                  <h3>{h}</h3>
                  <p>{t}</p>
                </div>
              ))}
            </div>
            <div className="lp-two">
              <div>
                <h3 className="lp-sub">What to expect</h3>
                <ul className="lp-list">
                  {nflExpect.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="lp-sub">How to play it for a better hit rate</h3>
                <ul className="lp-list">
                  {nflPlay.map(([h, t]) => (
                    <li key={h}>
                      <strong>{h}.</strong> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="lp-cta">
              <Link href="/nfl" className="lp-btn lp-btn-red">
                Open the NFL picks
              </Link>
            </div>
          </div>
        </section>

        {/* ---- plans ---- */}
        <section className="lp-band" id="plans">
          <div className="lp-wrap">
            <h2>Plans</h2>
            <div className="lp-plans">
              <div className="lp-plan">
                <h3>Pro</h3>
                <ul>
                  <li>Every NFL and NBA algorithm slip</li>
                  <li>Slip audits from a screenshot</li>
                  <li>Bankroll Strategy and bet tracking</li>
                  <li>{ADVISOR_LIMITS.dailyMessages.pro} advisor messages a day</li>
                </ul>
              </div>
              <div className="lp-plan lp-plan-top">
                <h3>Elite</h3>
                <ul>
                  <li>Everything in Pro</li>
                  <li>Unlimited advisor messages</li>
                  <li>Alerts when a saved leg is out, with a swap</li>
                </ul>
              </div>
            </div>
            <p className="lp-fine">Pricing and sign-up open at launch.</p>
          </div>
        </section>

        {/* ---- questions ---- */}
        <section className="lp-band lp-band-deep" id="faq">
          <div className="lp-wrap lp-faq">
            <h2>Questions</h2>
            <details>
              <summary>Is Godseye a sportsbook?</summary>
              <p>No. You cannot place a bet here. You bet with your own book and use Godseye to check the slip, size the stake and track the result.</p>
            </details>
            <details>
              <summary>Where do the picks come from?</summary>
              <p>From Godseye&apos;s own algorithms, one for each sport. There are no expert picks, media picks or consensus numbers anywhere on the site.</p>
            </details>
            <details>
              <summary>What does &quot;unrated&quot; mean?</summary>
              <p>The algorithm has no number for that leg, so it is left out of every calculation. Godseye never guesses to fill a gap.</p>
            </details>
            <details>
              <summary>How are stakes worked out?</summary>
              <p>A quarter of what the Kelly formula suggests, using the algorithm&apos;s chance and your book&apos;s price, capped by your risk profile and your own limits.</p>
            </details>
            <details>
              <summary>Do you promise winning bets?</summary>
              <p>No. Every slip shows its chance of losing, books price in an edge, and most bettors lose over time. The aim is better decisions, not guaranteed nights.</p>
            </details>
          </div>
        </section>
      </main>

      <SiteFooter>
        <Link href="/nfl">NFL</Link>
        <Link href="/nba">NBA</Link>
        <Link href="/nhl">NHL</Link>
        <a href="#picks">Algo Locks</a>
        <a href="#how">How it works</a>
        <a href="#mission">Mission</a>
        <a href="#faq">Questions</a>
      </SiteFooter>
    </div>
  );
}
