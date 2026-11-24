"use client";

/* The Paste a slip tab: read a slip from any book, review it from its prices, and show what the
   algorithm says about each leg. Used on both the NFL and the NBA side. */
import { useEffect, useMemo, useState } from "react";
import { decimalToAmerican, formatAmerican, parseSlip, type Bet, type Leg } from "@/lib/bets";
import { checkSlip } from "@/lib/slip";
import { SlipAudit } from "./SlipAudit";

const money = (n: number) => `${n < 0 ? "\u2212" : ""}$${Math.abs(n).toFixed(2)}`;

function Head({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        {sub && <p className="sub">{sub}</p>}
      </div>
    </div>
  );
}

/**
 * `defaultSport` is the side of the site the tab is on. `prefill` hands over legs from a model ticket;
 * `onPrefillUsed` tells the caller they have been taken.
 */
export function PasteTab({
  onSave,
  bets,
  defaultSport = "NFL",
  prefill,
  onPrefillUsed,
}: {
  onSave: (b: Bet) => void;
  bets: Bet[];
  defaultSport?: "NFL" | "NBA";
  prefill?: Leg[] | null;
  onPrefillUsed?: () => void;
}) {
  const [text, setText] = useState("");
  const [legs, setLegs] = useState<Leg[]>(() => prefill ?? []);
  useEffect(() => {
    onPrefillUsed?.();
    // only once, when the tab opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [stake, setStake] = useState("25");
  const [book, setBook] = useState("bet365");
  const [sport, setSport] = useState<string>(defaultSport);
  const [parseMsg, setParseMsg] = useState("");

  const stakeNum = Number(stake) > 0 ? Number(stake) : 0;
  const valid = useMemo(
    () => legs.filter((l) => Number.isFinite(l.odds) && Math.abs(l.odds) >= 100),
    [legs],
  );
  const review = useMemo(() => checkSlip(valid, stakeNum), [valid, stakeNum]);

  const readText = () => {
    const found = parseSlip(text);
    if (!found.length) {
      setParseMsg(
        "No legs found. Put each leg on its own line and end it with the odds, like: Bills -3.5 -110",
      );
      return;
    }
    setParseMsg("");
    setLegs((prev) => [...prev, ...found]);
    setText("");
  };
  const update = (i: number, patch: Partial<Leg>) =>
    setLegs((prev) => prev.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  return (
    <div className="t-cols">
      <section className="panel">
        <Head
          title="Paste a slip"
          sub="For any bet from any book or sport, including ones the model does not cover. One leg per line, odds last."
        />
        <label className="t-field">
          <span>Your slip</span>
          <textarea
            rows={4}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={
              defaultSport === "NBA"
                ? "Andrew Nembhard 6+ Assists -288\nPascal Siakam 20+ Points -150"
                : "Bills -3.5 -110\nJosh Allen 225+ Passing Yards -115"
            }
          />
        </label>
        {parseMsg && <p className="t-err">{parseMsg}</p>}
        <div className="t-row">
          <button className="btn primary" onClick={readText}>
            Add legs
          </button>
          <button
            className="btn"
            onClick={() => setLegs((p) => [...p, { description: "", odds: -110 }])}
          >
            Add a leg by hand
          </button>
        </div>

        {legs.map((l, i) => (
          <div className="t-leg" key={i}>
            <label className="t-field t-grow">
              <span>Leg {i + 1}</span>
              <input
                value={l.description}
                onChange={(e) => update(i, { description: e.target.value })}
                placeholder={defaultSport === "NBA" ? "Pascal Siakam 20+ Points" : "Bills -3.5"}
              />
            </label>
            <label className="t-field t-narrow">
              <span>Odds</span>
              <input
                inputMode="numeric"
                value={Number.isFinite(l.odds) ? String(l.odds) : ""}
                onChange={(e) =>
                  update(i, { odds: e.target.value === "" ? NaN : Number(e.target.value) })
                }
              />
            </label>
            <label className="t-field t-mid">
              <span>Game (optional)</span>
              <input
                value={l.game ?? ""}
                onChange={(e) => update(i, { game: e.target.value })}
                placeholder={defaultSport === "NBA" ? "OKC @ IND" : "BUF @ MIA"}
              />
            </label>
            <button
              className="t-x"
              aria-label={`Remove leg ${i + 1}`}
              onClick={() => setLegs((p) => p.filter((_, j) => j !== i))}
            >
              Remove
            </button>
          </div>
        ))}

        {legs.length > 0 && (
          <div className="t-leg">
            <label className="t-field t-narrow">
              <span>Stake ($)</span>
              <input inputMode="decimal" value={stake} onChange={(e) => setStake(e.target.value)} />
            </label>
            <label className="t-field t-mid">
              <span>Sportsbook</span>
              <input value={book} onChange={(e) => setBook(e.target.value)} />
            </label>
            <label className="t-field t-narrow">
              <span>Sport</span>
              <select value={sport} onChange={(e) => setSport(e.target.value)}>
                <option>NFL</option>
                <option>NBA</option>
                <option>Other</option>
              </select>
            </label>
          </div>
        )}
      </section>

      <section className="panel">
        {valid.length === 0 ? (
          <>
            <Head title="Review" />
            <p className="empty">
              Add at least one leg and the review appears here: payout, what the prices imply, and
              anything worth a second look.
            </p>
          </>
        ) : (
          <>
            <Head
              title={`${valid.length === 1 ? "Single" : `${valid.length}-leg parlay`} at ${formatAmerican(decimalToAmerican(review.decimal))}`}
            />
            <p className="t-big num">
              {money(stakeNum)} to win {money(review.toWin)}
            </p>
            <ul className="t-findings">
              {review.findings.map((f, i) => (
                <li key={i} className={f.level}>
                  <strong>{f.title}</strong>
                  <span>{f.detail}</span>
                </li>
              ))}
            </ul>
            <SlipAudit legs={valid} sport={sport} bets={bets} />
            <button
              className="btn primary"
              style={{ marginTop: 14 }}
              disabled={stakeNum <= 0}
              onClick={() =>
                onSave({
                  id: crypto.randomUUID(),
                  placedAt: new Date().toISOString(),
                  sport,
                  book: book.trim(),
                  legs: valid.map((l) => ({ ...l, description: l.description.trim() || "Leg" })),
                  stake: stakeNum,
                  status: "open",
                })
              }
            >
              Save to my bets
            </button>
            {stakeNum <= 0 && <p className="t-err">Enter a stake above zero to save this bet.</p>}
          </>
        )}
      </section>
    </div>
  );
}
