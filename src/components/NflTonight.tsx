/* Today's NFL slips (model/output/nfl_today.json, written by scripts/nfl-slate.sh): one pack per game, every leg a
   rung a sportsbook lists, every chance the NFL algorithm's. The algorithm's pick in each tier is outlined. */
import raw from "../../model/output/nfl_today.json";
import { Slip, american, pct } from "@/components/Slip";

type Leg = { text: string; p: number; record?: string; listed?: string; why?: string[] };
type S = { title: string; kind?: string; pick: boolean; p: number; fair: number; listedMultiplied?: number | null; legs: Leg[]; note?: string };
type Single = { name: string; team: string; pos: string; p: number; fair: number; flag: string; listed: string; why: string[] };
type Game = {
  game: string; game_id: string; kickoff: string; venue: string; listings: { source: string; pulled_at: string };
  sgps: S[]; hybrids: S[]; lotto: S | null; rush?: S[];
  atd: { singles: Single[]; double: S | null; held: { name: string; why: string }[] };
};
type Today = {
  made_at: string; built_from: string; rules: string[]; listings: { source: string; pulled_at: string }; games: Game[];
};
const T = raw as unknown as Today;
const et = (iso: string) => new Date(iso).toLocaleTimeString("en-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });

function Card({ s, game }: { s: S; game: string }) {
  return (
    <Slip
      badge={s.pick ? "Algo pick" : "Godseye slip"}
      pick={s.pick}
      title={s.title}
      meta={game}
      legs={s.legs.map((l) => ({ text: l.text, sub: [l.record, l.listed ? `listed ${l.listed}` : ""].filter(Boolean).join(" · ") || undefined, value: pct(l.p) }))}
      why={{ legs: s.legs.map((l) => ({ text: l.text, why: l.why ?? [] })) }}
      stats={[
        { label: "Chance to hit", value: pct(s.p, 1), tone: "red" },
        { label: "Chance to miss", value: pct(1 - s.p, 1) },
        { label: "Books' leg prices combined", value: s.listedMultiplied == null ? "–" : american(s.listedMultiplied) },
      ]}
      note={s.note}
    />
  );
}

function Tier({ title, sub, slips, game }: { title: string; sub?: string; slips: S[]; game: string }) {
  if (!slips.length) return null;
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {sub && <p className="sub">{sub}</p>}
        </div>
      </div>
      <div className="gs-slips ge-set">
        {slips.map((s, i) => (
          <Card s={s} game={game} key={i} />
        ))}
      </div>
    </section>
  );
}

const bySize = (list: S[]) => [...new Set(list.map((s) => s.title))].map((t) => list.filter((s) => s.title === t));

function GamePack({ g }: { g: Game }) {
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>{g.game}</h2>
            <p className="sub">
              {g.kickoff} · {g.venue}. Prices pulled {et(g.listings.pulled_at)} ET.
            </p>
          </div>
        </div>
      </section>
      {bySize(g.rush ?? []).map((x) => (
        <Tier key={x[0].title} game={g.game} title={`${g.game}: ${x[0].title}`} sub={x[0].kind === "rush_td" ? "Rushing legs plus one anytime TD from a scorer whose matchup clears." : "Rushing legs only: the backs in the weather."} slips={x} />
      ))}
      {bySize(g.sgps).map((x) => (
        <Tier key={x[0].title} game={g.game} title={`${g.game}: ${x[0].title}`} sub="Props only, no touchdown legs." slips={x} />
      ))}
      {bySize(g.hybrids).map((x) => (
        <Tier key={x[0].title} game={g.game} title={`${g.game}: ${x[0].title}`} sub="Props legs plus one anytime touchdown." slips={x} />
      ))}
      {g.lotto && <Tier game={g.game} title={`${g.game}: lotto`} sub="A longshot: the algorithm makes it 1 in 16 or less likely, and the books' leg prices combine to +1500 or longer." slips={[g.lotto]} />}
    </>
  );
}

export function NflTonight() {
  const made = new Date(T.made_at).toLocaleString("en-CA", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" });
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Today: {T.games.map((g) => g.game).join(" · ")}</h2>
            <p className="sub">
              Made {made} ET from the algorithm&apos;s build of {T.built_from}. One pack per game. Each leg is set by its matchup and carries the price a sportsbook
              lists for that rung. The slip outlined in red in each tier is the algorithm&apos;s pick.
            </p>
          </div>
        </div>
        <ul className="why">
          {T.rules.map((r) => (
            <li key={r}>{r}</li>
          ))}
          <li>Touchdown-only slips (singles, doubles, triples and longer) are on the Anytime TD tab.</li>
          <li>Prices from {T.listings.source}. &ldquo;Books&apos; leg prices combined&rdquo; multiplies each leg&apos;s listed price; a book prices the same legs as a same-game parlay shorter than that.</li>
        </ul>
      </section>
      {T.games.map((g) => (
        <GamePack g={g} key={g.game_id} />
      ))}
    </>
  );
}
