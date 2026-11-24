"use client";

/* Audit a slip from a screenshot: upload, confirm what was read, grade, and compare with the
   algorithm's improved slip. Every number shown comes from src/lib/slip (the algorithms' output and
   the correlation engine) and src/lib/staking. The screenshot reader only transcribes. */
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { MARKET_LABEL, type Catalog, type Market, type RatedLeg, type Sport } from "@/lib/advisor/legs";
import { formatAmerican, type Bet } from "@/lib/bets";
import { gradeSlip, type SlipGrade } from "@/lib/slip/grade";
import { recheckAll, toSavedLeg, type SavedSlip, type SlipAlert } from "@/lib/slip/recheck";
import { MARKET_VALUES, legNeeds, oddsToAmerican, type DraftLeg, type SlipDraft } from "@/lib/slip/schema";
import { legLabel, suggestChanges, type Suggestions } from "@/lib/slip/suggest";
import { draftToInput } from "@/lib/slip/tools";
import { sizeBet, tonightFrom, type Sizing } from "@/lib/staking";
import { readAccount, subscribeAccount } from "./BankrollStrategy";
import { loadCatalog } from "./SlipAudit";
import { NO_BETS, readBets, subscribeBets, writeBets } from "./betsStore";

// ---------- saved slips (this browser's storage, until accounts exist) ----------
const SLIPS = "godseye.slips.v1";
function readSlips(): SavedSlip[] {
  try {
    const raw = JSON.parse(localStorage.getItem(SLIPS) ?? "[]");
    return Array.isArray(raw) ? (raw as SavedSlip[]) : [];
  } catch {
    return [];
  }
}
function writeSlips(next: SavedSlip[]) {
  try {
    localStorage.setItem(SLIPS, JSON.stringify(next.slice(0, 50)));
  } catch {
    /* storage unavailable */
  }
}

const pct = (p: number | null | undefined, d = 1) => (p == null ? "–" : `${(p * 100).toFixed(d)}%`);
const odds = (a: number | null | undefined) => (a == null ? "–" : formatAmerican(a));
const pts = (e: number) => `${e >= 0 ? "+" : "−"}${Math.abs(e * 100).toFixed(1)} pts`;
const MARKET_OPTIONS = MARKET_VALUES.filter((m) => m !== "other") as Market[];

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

function stakeLine(s: Sizing | null, hasAccount: boolean) {
  if (!hasAccount) return "set a bankroll first";
  if (!s) return "–";
  return s.status === "bet" ? s.label : s.status === "unrated" ? "unrated" : s.status === "blocked" ? "none: a limit is in force" : "no bet at this price";
}

type Step = "upload" | "confirm" | "result";

export function ScreenshotAudit({ defaultSport = "NFL" }: { defaultSport?: Sport }) {
  const [step, setStep] = useState<Step>("upload");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<SlipDraft | null>(null);
  const [sport, setSport] = useState<Sport>(defaultSport);
  const [legCount, setLegCount] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [newPrice, setNewPrice] = useState("");
  const [logged, setLogged] = useState("");
  const [alerts, setAlerts] = useState<SlipAlert[]>([]);
  const account = useSyncExternalStore(subscribeAccount, readAccount, () => null);
  const bets = useSyncExternalStore(subscribeBets, readBets, () => NO_BETS);
  const [now] = useState(() => new Date());

  useEffect(() => {
    let live = true;
    loadCatalog(sport).then(
      (c) => {
        if (!live) return;
        setCatalog(c);
        setCatalogFailed(false);
        setAlerts(recheckAll(readSlips(), c));
      },
      () => live && setCatalogFailed(true),
    );
    return () => {
      live = false;
    };
  }, [sport]);

  const money = useMemo(() => (account ? { account, tonight: tonightFrom(bets, now), now } : {}), [account, bets, now]);
  const result = useMemo(() => {
    if (step !== "result" || !draft || !catalog) return null;
    const grade: SlipGrade = gradeSlip(draftToInput(draft), catalog, { totalOdds: draft.totalOdds, ...money });
    const wanted = Number(legCount);
    const suggestions: Suggestions = suggestChanges(grade, catalog, { legCount: wanted >= 1 ? Math.round(wanted) : null, book: draft.book });
    return { grade, suggestions };
  }, [step, draft, catalog, legCount, money]);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError("");
    setLogged("");
    try {
      const body = new FormData();
      body.append("image", file);
      const res = await fetch("/api/slip/parse", { method: "POST", body });
      const json = (await res.json().catch(() => null)) as { draft?: SlipDraft; error?: string } | null;
      if (!res.ok || !json?.draft) throw new Error(json?.error ?? "The screenshot reader is not available here.");
      setDraft(json.draft);
      const first = json.draft.legs.find((l) => l.sport === "NFL" || l.sport === "NBA")?.sport;
      if (first === "NFL" || first === "NBA") setSport(first);
      setNewPrice("");
      setStep("confirm");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong reading that screenshot.");
    } finally {
      setBusy(false);
    }
  };

  const editLeg = (i: number, patch: Partial<DraftLeg>) =>
    setDraft((d) => {
      if (!d) return d;
      const legs = d.legs.map((l, j) => {
        if (j !== i) return l;
        const next = { ...l, ...patch };
        return { ...next, needs: legNeeds(next) };
      });
      return { ...d, legs };
    });
  const blank: DraftLeg = { sport, game: null, player: "", market: null, marketText: "", threshold: null, side: "over", odds: null, needs: ["player", "market"] };
  const pending = draft ? draft.legs.filter((l) => l.needs.length > 0).length : 0;

  const log = (legs: { description: string; odds: number }[], price: number | null, chance: number | null, stakeDollars: number, rated: RatedLeg[]) => {
    const id = crypto.randomUUID();
    const bet: Bet = { id, placedAt: new Date().toISOString(), sport, book: draft?.book ?? "", legs, stake: stakeDollars, status: "open",
                       ...(price != null ? { price } : {}), ...(chance != null ? { modelChance: chance } : {}) };
    writeBets([bet, ...readBets()]);
    if (catalog && rated.length)
      writeSlips([{ id: crypto.randomUUID(), savedAt: bet.placedAt, sport, built: catalog.built, betId: id, legs: rated.map((l) => toSavedLeg(l)) }, ...readSlips()]);
    setLogged("Logged to My bets. It will be re-checked whenever the algorithm's numbers are rebuilt.");
  };

  return (
    <>
      {alerts.length > 0 && (
        <section className="panel">
          <Head title="A saved slip needs a look" sub="The algorithm's numbers have been rebuilt since you saved it." />
          <ul className="t-findings">
            {alerts.map((a, i) => (
              <li key={i} className="warn">
                <strong>{a.title}</strong>
                <span>
                  {a.detail} {a.swap ? `Here is a swap from the algorithm: ${legLabel(a.swap)} (${pct(a.swap.prob, 0)}).` : "The algorithm has no replacement that passes the ticket rules."}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {step === "upload" && (
        <section className="panel">
          <Head
            title="Audit a screenshot"
            sub="Upload a screenshot of your own bet slip. You confirm what was read, then the algorithm grades it and suggests what to remove, swap or add."
          />
          <label className="t-field">
            <span>Bet slip screenshot (bet365 works best; PNG or JPEG, up to 5 MB)</span>
            <input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={(e) => upload(e.target.files?.[0])} />
          </label>
          {busy && <p className="sub">Reading your slip…</p>}
          {error && (
            <p className="t-err">
              {error} You can also type the slip in <a href="#paste">Paste a slip</a>.
            </p>
          )}
          <p className="t-note">
            The screenshot is sent to the reader to be transcribed and is not kept. Crop out your name and balance if they are in the picture.
          </p>
        </section>
      )}

      {step === "confirm" && draft && (
        <section className="panel">
          <Head title="Is this your slip?" sub="Check each leg and fix anything that was misread. Nothing is graded until you confirm." />
          {draft.problems.length > 0 && (
            <div className="warns">
              {draft.problems.map((p) => (
                <div key={p}>{p}</div>
              ))}
            </div>
          )}
          {draft.legs.map((l, i) => (
            <div className="t-leg" key={i}>
              <label className="t-field t-grow">
                <span>
                  Leg {i + 1}
                  {l.needs.length > 0 && ` · could not read: ${l.needs.join(", ")}`}
                </span>
                <input value={l.player ?? ""} placeholder={l.market === "other" ? l.marketText : "Player"} onChange={(e) => editLeg(i, { player: e.target.value || null })} />
              </label>
              <label className="t-field t-mid">
                <span>Market</span>
                <select value={l.market ?? ""} onChange={(e) => editLeg(i, { market: (e.target.value || null) as DraftLeg["market"], threshold: e.target.value === "atd" ? null : l.threshold })}>
                  <option value="">Choose…</option>
                  {MARKET_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      {MARKET_LABEL[m]}
                    </option>
                  ))}
                  <option value="other">Other (not a player prop)</option>
                </select>
              </label>
              <label className="t-field t-narrow">
                <span>{l.side === "under" ? "Under" : "At least"}</span>
                <input
                  inputMode="decimal"
                  disabled={l.market === "atd"}
                  value={l.threshold ?? ""}
                  placeholder={l.market === "atd" ? "n/a" : "225"}
                  onChange={(e) => editLeg(i, { threshold: e.target.value === "" || !Number.isFinite(Number(e.target.value)) ? null : Number(e.target.value) })}
                />
              </label>
              <label className="t-field t-narrow">
                <span>Leg price</span>
                <input defaultValue={l.odds ?? ""} placeholder="none" onBlur={(e) => editLeg(i, { odds: oddsToAmerican(e.target.value) })} />
              </label>
              <button className="t-x" aria-label={`Remove leg ${i + 1}`} onClick={() => setDraft({ ...draft, legs: draft.legs.filter((_, j) => j !== i) })}>
                Remove
              </button>
            </div>
          ))}
          <div className="t-leg">
            <label className="t-field t-narrow">
              <span>Slip price</span>
              <input key={draft.totalOdds ?? "none"} defaultValue={draft.totalOdds ?? ""} placeholder="+450" onBlur={(e) => setDraft({ ...draft, totalOdds: oddsToAmerican(e.target.value) })} />
            </label>
            <label className="t-field t-narrow">
              <span>Stake ($)</span>
              <input inputMode="decimal" defaultValue={draft.stake ?? ""} onBlur={(e) => setDraft({ ...draft, stake: Number(e.target.value) > 0 ? Number(e.target.value) : null })} />
            </label>
            <label className="t-field t-mid">
              <span>Sportsbook</span>
              <input defaultValue={draft.book ?? ""} onBlur={(e) => setDraft({ ...draft, book: e.target.value.trim() || null })} />
            </label>
            <label className="t-field t-narrow">
              <span>Sport</span>
              <select value={sport} onChange={(e) => setSport(e.target.value as Sport)}>
                <option>NFL</option>
                <option>NBA</option>
              </select>
            </label>
            <label className="t-field t-narrow">
              <span>Legs you want</span>
              <input inputMode="numeric" value={legCount} placeholder={String(draft.legs.length)} onChange={(e) => setLegCount(e.target.value)} />
            </label>
          </div>
          {catalogFailed && <p className="t-err">The {sport} algorithm&apos;s numbers did not load, so this slip cannot be graded right now.</p>}
          <div className="t-row">
            <button className="btn primary" disabled={!draft.legs.length || !catalog} onClick={() => setStep("result")}>
              Yes, grade this slip
            </button>
            <button className="btn" onClick={() => setDraft({ ...draft, legs: [...draft.legs, blank] })}>
              Add a leg
            </button>
            <button className="btn" onClick={() => setStep("upload")}>
              Upload a different screenshot
            </button>
          </div>
          {pending > 0 && (
            <p className="sub">
              {pending} leg{pending > 1 ? "s still need" : " still needs"} something filled in. A leg left incomplete is graded as unrated and left out of the numbers.
            </p>
          )}
        </section>
      )}

      {step === "result" && draft && result && catalog && (
        <ResultView
          draft={draft}
          grade={result.grade}
          suggestions={result.suggestions}
          newPrice={newPrice}
          setNewPrice={setNewPrice}
          hasAccount={!!account}
          improvedStake={(price, prob) => (account ? sizeBet({ prob, price }, account, tonightFrom(bets, now), now) : null)}
          logged={logged}
          onBack={() => setStep("confirm")}
          onLog={log}
        />
      )}
    </>
  );
}

function ResultView({
  draft, grade, suggestions, newPrice, setNewPrice, hasAccount, improvedStake, logged, onBack, onLog,
}: {
  draft: SlipDraft;
  grade: SlipGrade;
  suggestions: Suggestions;
  newPrice: string;
  setNewPrice: (s: string) => void;
  hasAccount: boolean;
  improvedStake: (price: number | null, prob: number | null) => Sizing | null;
  logged: string;
  onBack: () => void;
  onLog: (legs: { description: string; odds: number }[], price: number | null, chance: number | null, stake: number, rated: RatedLeg[]) => void;
}) {
  const imp = suggestions.improved;
  const price = oddsToAmerican(newPrice);
  const impComplete = !!imp && imp.unratedKept.length === 0 && imp.joint !== null;
  const impStake = imp ? improvedStake(price, impComplete ? imp.joint : null) : null;
  const impValue = imp && impComplete && price !== null ? (imp.joint as number) * (price > 0 ? 1 + price / 100 : 1 + 100 / -price) - 1 : null;
  const originalRated = grade.legs.filter((l) => l.status === "rated" && l.match).map((l) => l.match as RatedLeg);
  const dollars = (s: Sizing | null) => (s?.status === "bet" && s.dollars ? s.dollars : (draft.stake ?? 0));

  return (
    <>
      <section className="panel">
        <Head title="Your slip, leg by leg" sub={`${grade.rated} of ${grade.legs.length} legs rated · ${grade.sport} algorithm built ${grade.built}`} />
        <div className="scroll">
          <table className="tbl">
            <thead>
              <tr>
                {["Leg", "Algorithm", "Price implies", "Edge", "Notes"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grade.legs.map((l, i) => (
                <tr key={i}>
                  <td>
                    <b>{l.match ? legLabel(l.match) : l.text}</b>
                  </td>
                  <td className="num">{l.status === "rated" ? pct(l.prob) : "unrated"}</td>
                  <td className="num">{pct(l.implied)}</td>
                  <td className="num">{l.edge == null ? "–" : pts(l.edge)}</td>
                  <td>
                    {l.status !== "rated" && l.note}
                    {l.match?.games != null && l.match.hits != null && `Cleared in ${l.match.hits} of ${l.match.games} games. `}
                    {l.injury && `Listed ${l.injury}. `}
                    {l.flags.includes("fights-script") && "Works against your other legs. "}
                    {l.flags.includes("singles-only") && "Singles only this week. "}
                    {l.risk && `Risk: ${l.risk}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {grade.rules.length > 0 && (
          <ul className="t-findings" style={{ marginTop: 12 }}>
            {grade.rules.map((r) => (
              <li key={r.rule} className={r.level}>
                <strong>{r.level === "warn" ? "Outside Godseye's ticket rules" : "Worth knowing"}</strong>
                <span>{r.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="t-cols">
        <section className="panel">
          <Head title="Your slip" sub={`${grade.legs.length} leg${grade.legs.length > 1 ? "s" : ""}`} />
          <dl className="kv">
            <dt>Chance to hit</dt>
            <dd>{grade.joint == null ? "not stated" : pct(grade.joint)}</dd>
            <dt>Fair odds</dt>
            <dd>{odds(grade.fairOdds)}</dd>
            <dt>Book odds</dt>
            <dd>{odds(grade.bookOdds)}</dd>
            <dt>Value at the book&apos;s price</dt>
            <dd className={grade.value == null ? undefined : grade.value > 0 ? "t-up" : "t-down"}>{grade.value == null ? "not stated" : `${grade.value >= 0 ? "+" : "−"}${Math.abs(grade.value * 100).toFixed(1)}%`}</dd>
            <dt>Suggested stake</dt>
            <dd>{stakeLine(grade.stake, hasAccount)}</dd>
          </dl>
          <p className="sub">{grade.jointNote}</p>
          <p className="sub">{grade.valueNote}</p>
          <div className="t-row">
            <button
              className="btn"
              onClick={() => onLog(grade.legs.map((l) => ({ description: l.match ? legLabel(l.match) : l.text, odds: l.odds ?? 0 })), grade.bookOdds, grade.unrated === 0 ? grade.joint : null, dollars(grade.stake), originalRated)}
            >
              Log my slip as it is
            </button>
          </div>
        </section>

        <section className="panel">
          <Head title="Improved slip" sub={imp ? `${imp.legs.length + imp.unratedKept.length} legs · algorithm output only` : "No changes suggested"} />
          {!imp && <p className="empty">{suggestions.notes[0]}</p>}
          {imp && (
            <>
              {imp.legs.map((l) => (
                <div className="t-bet-leg" key={legLabel(l)}>
                  <span>{legLabel(l)}</span>
                  <span className="num">{pct(l.prob, 0)}</span>
                </div>
              ))}
              {imp.unratedKept.map((t) => (
                <div className="t-bet-leg" key={t}>
                  <span>{t}</span>
                  <span className="num">unrated</span>
                </div>
              ))}
              <dl className="kv" style={{ marginTop: 12 }}>
                <dt>Chance to hit</dt>
                <dd>{imp.joint == null ? "not stated" : pct(imp.joint)}</dd>
                <dt>Fair odds</dt>
                <dd>{odds(imp.fairOdds)}</dd>
                <dt>Book odds</dt>
                <dd>{price == null ? "type the new price" : odds(price)}</dd>
                <dt>Value at the book&apos;s price</dt>
                <dd className={impValue == null ? undefined : impValue > 0 ? "t-up" : "t-down"}>{impValue == null ? "not stated" : `${impValue >= 0 ? "+" : "−"}${Math.abs(impValue * 100).toFixed(1)}%`}</dd>
                <dt>Suggested stake</dt>
                <dd>{price == null ? "needs the new price" : stakeLine(impStake, hasAccount)}</dd>
              </dl>
              <label className="t-field" style={{ marginTop: 12 }}>
                <span>Your book&apos;s price for the improved slip</span>
                <input value={newPrice} placeholder="+380" onChange={(e) => setNewPrice(e.target.value)} />
              </label>
              <p className="sub">{imp.note}</p>
              <div className="t-row">
                <button
                  className="btn primary"
                  disabled={price == null}
                  onClick={() => onLog([...imp.legs.map((l) => ({ description: legLabel(l), odds: 0 })), ...imp.unratedKept.map((t) => ({ description: t, odds: 0 }))], price, impComplete ? imp.joint : null, dollars(impStake), imp.legs)}
                >
                  Accept changes and log the bet
                </button>
              </div>
              {price == null && <p className="sub">Build the improved slip at your book, then type its price here to log it.</p>}
            </>
          )}
        </section>
      </div>

      {(suggestions.remove.length > 0 || suggestions.swap.length > 0 || suggestions.add.length > 0) && (
        <section className="panel">
          <Head title="What changed, and why" />
          <ul className="t-findings">
            {suggestions.remove.map((r) => (
              <li key={`r${r.index}`} className="warn">
                <strong>Remove: {legLabel(r.leg)}</strong>
                <span>{r.reason}</span>
              </li>
            ))}
            {suggestions.swap.map((s) => (
              <li key={`s${s.index}`} className="info">
                <strong>
                  Swap: {legLabel(s.from)} for {legLabel(s.to)}
                </strong>
                <span>{s.reason}</span>
              </li>
            ))}
            {suggestions.add.map((a) => (
              <li key={legLabel(a.leg)} className="info">
                <strong>Add: {legLabel(a.leg)}</strong>
                <span>{a.reason}</span>
              </li>
            ))}
          </ul>
          {suggestions.notes.map((n) => (
            <p className="sub" key={n}>
              {n}
            </p>
          ))}
        </section>
      )}

      <section className="panel">
        {logged && <p className="sub">{logged}</p>}
        <div className="t-row">
          <button className="btn" onClick={onBack}>
            Back to edit the legs
          </button>
          <a className="btn" href="#bets">
            My bets
          </a>
        </div>
        <p className="t-note">
          An audit is information, not a promise. A slip the algorithm likes still loses, and a parlay loses more often than it wins. Bet smarter, survive the variance.
        </p>
      </section>
    </>
  );
}
