import metrics from "../../model/output/team_metrics.json";

type TeamRow = (typeof metrics.teams)[keyof typeof metrics.teams];
const teams = metrics.teams as Record<string, TeamRow>;
const lg = metrics.league_average;
const v = metrics.validation;

const signed = (n: number, digits = 1) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(digits)}`;
const american = (n: number) => (n > 0 ? `+${n}` : `−${Math.abs(n)}`);
const clock = (minutes: number) => {
  const total = Math.round(minutes * 60);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};
const pctBetter = (skill: number) => `${(skill * 100).toFixed(1)}%`;

function spreadLabel(home: string, away: string, homeSpread: number) {
  if (homeSpread === 0) return "Pick'em";
  return homeSpread < 0 ? `${home} −${Math.abs(homeSpread)}` : `${away} −${homeSpread}`;
}

/** Flags a side whose expected penalties sit clearly above or below the league average. */
function penaltyPill(value: number, average: number) {
  const diff = value - average;
  if (diff >= 0.35) return <span className="pill bad">high</span>;
  if (diff <= -0.35) return <span className="pill good">low</span>;
  return null;
}

export function ScriptsTab() {
  const ranked = Object.entries(teams).sort((a, b) => a[1].top_offence_rank - b[1].top_offence_rank);
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>
              Game scripts, {metrics.as_of.season} week {metrics.as_of.through_week + 1}
            </h2>
            <p className="sub">
              Market lines for each game, with projected time of possession and expected offensive
              and defensive penalties. Built from every play of {metrics.as_of.seasons_used}, with
              recent games weighted more and each team adjusted for the opponents it faced.
            </p>
          </div>
        </div>
        <div className="warns">
          <div>
            How much to trust these: possession and penalties are mostly noise from game to game.
            Tested on {v.top_share_with_spread.games} games ({v.test_seasons}) the model never saw,
            the possession forecast beat a plain 30:00 each guess by{" "}
            {pctBetter(v.top_share_with_spread.skill_vs_league_average)}, and most of that comes
            from the point spread. Penalty forecasts beat the league average by{" "}
            {pctBetter(v.def_pen.skill_vs_league_average)} (defence) and{" "}
            {pctBetter(v.off_pen.skill_vs_league_average)} (offence). Use them as context for a
            game script, not as an edge on their own.
          </div>
        </div>
      </section>

      {metrics.games.map((g) => {
        const m = g.market;
        const share = g.possession.home_share;
        return (
          <section className="panel" key={g.game_id}>
            <div className="section-head">
              <div>
                <h2>
                  {g.away} @ {g.home}
                </h2>
                <p className="sub">{g.gameday}</p>
              </div>
            </div>
            <div className="envline">
              {m ? (
                <>
                  <span className="pill gold">{spreadLabel(g.home, g.away, m.home_spread)}</span>
                  <span className="pill">Total {m.total}</span>
                  <span className="pill">
                    Implied {g.away} {m.away_implied_points} / {g.home} {m.home_implied_points}
                  </span>
                  {"home_moneyline" in m && m.home_moneyline != null && (
                    <>
                      <span className="pill">
                        Moneyline {g.away} {american(m.away_moneyline as number)} / {g.home}{" "}
                        {american(m.home_moneyline as number)}
                      </span>
                      <span className="pill">
                        {g.home} wins {((m.home_win_chance_no_margin as number) * 100).toFixed(1)}%
                        with the book&apos;s margin removed
                      </span>
                    </>
                  )}
                </>
              ) : (
                <span className="pill warn">No market lines posted yet</span>
              )}
            </div>

            <h3 style={{ marginTop: 14 }}>Projected time of possession</h3>
            <div className="t-poss" role="img" aria-label={`${g.away} ${clock(g.possession.away_minutes)}, ${g.home} ${clock(g.possession.home_minutes)}`}>
              <span className="t-poss-a" style={{ width: `${(1 - share) * 100}%` }}>
                {g.away} {clock(g.possession.away_minutes)}
              </span>
              <span className="t-poss-h" style={{ width: `${share * 100}%` }}>
                {g.home} {clock(g.possession.home_minutes)}
              </span>
            </div>
            <p className="sub">Based on {g.possession.basis}.</p>

            <h3 style={{ marginTop: 14 }}>Expected penalties</h3>
            <div className="scroll">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Team</th>
                    <th>On offence</th>
                    <th>Yards</th>
                    <th>On defence</th>
                    <th>Yards</th>
                  </tr>
                </thead>
                <tbody>
                  {([
                    [g.away, g.penalties.away],
                    [g.home, g.penalties.home],
                  ] as const).map(([team, p]) => (
                    <tr key={team}>
                      <td>
                        <b>{team}</b>
                      </td>
                      <td className="num">
                        {p.off_pen.toFixed(1)} {penaltyPill(p.off_pen, lg.off_pen_per_game)}
                      </td>
                      <td className="num">{p.off_pen_yds.toFixed(0)}</td>
                      <td className="num">
                        {p.def_pen.toFixed(1)} {penaltyPill(p.def_pen, lg.def_pen_per_game)}
                      </td>
                      <td className="num">{p.def_pen_yds.toFixed(0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Team ratings</h2>
            <p className="sub">
              Possession is seconds per drive against an average opponent, compared with the league
              average of {lg.sec_per_drive.toFixed(0)} seconds. Offence: higher holds the ball
              longer. Defence: lower gets off the field sooner. Penalties are per game against an
              average opponent; league averages are {lg.off_pen_per_game.toFixed(1)} on offence and{" "}
              {lg.def_pen_per_game.toFixed(1)} on defence. Rank 1 is best.
            </p>
          </div>
        </div>
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                <th>Team</th>
                <th>Possession, offence</th>
                <th>Possession, defence</th>
                <th>Possession share this season</th>
                <th>Offensive penalties</th>
                <th>Defensive penalties</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(([t, r]) => (
                <tr key={t}>
                  <td>
                    <b>{t}</b>
                  </td>
                  <td className="num">
                    {signed(r.top_offence_sec_per_drive)}s <span className="sub">#{r.top_offence_rank}</span>
                  </td>
                  <td className="num">
                    {signed(r.top_defence_sec_per_drive)}s <span className="sub">#{r.top_defence_rank}</span>
                  </td>
                  <td className="num">{(r.top_share_this_season * 100).toFixed(1)}%</td>
                  <td className="num">
                    {r.off_pen_per_game.toFixed(1)} <span className="sub">#{r.off_pen_rank}</span>
                  </td>
                  <td className="num">
                    {r.def_pen_per_game.toFixed(1)} <span className="sub">#{r.def_pen_rank}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
