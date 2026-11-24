"use client";

/* The Bankroll Strategy tab. It only collects settings and shows results:
   every stake number comes from src/lib/staking.ts, the one staking engine. */
import { useState, useSyncExternalStore } from "react";
import { decimalToAmerican, formatAmerican, type Bet } from "@/lib/bets";
import {
  CUSTOM_BOUNDS,
  CUSTOM_DEFAULT,
  PROFILES,
  clampCustom,
  termsOf,
  type CustomProfile,
  type PresetId,
  checkLimits,
  formatStake,
  openAccount,
  sizeBet,
  tonightFrom,
  unitFor,
  withWeeklyUnit,
  type Account,
  type Limits,
  type ProfileId,
  type Sizing,
} from "@/lib/staking";

// ---------- the account (this browser's storage, until logins exist) ----------
const STORE = "godseye.bankroll.v1";
const listeners = new Set<() => void>();
let cache: Account | null | undefined;

function valid(a: unknown): a is Account {
  const x = a as Account;
  return (
    !!x &&
    typeof x.bankroll === "number" &&
    x.bankroll >= 0 &&
    (x.profile === "custom" || x.profile in PROFILES) &&
    typeof x.limits === "object" &&
    x.limits !== null
  );
}
export function readAccount(): Account | null {
  if (cache === undefined) {
    try {
      const raw = JSON.parse(localStorage.getItem(STORE) ?? "null");
      cache = valid(raw) ? raw : null;
    } catch {
      cache = null;
    }
  }
  return cache;
}
function writeAccount(next: Account) {
  cache = next;
  try {
    localStorage.setItem(STORE, JSON.stringify(next));
  } catch {
    /* storage unavailable: keep in memory for this visit */
  }
  listeners.forEach((l) => l());
}
export function subscribeAccount(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

// ---------- the bet slip the console is showing right now ----------
export type SlipQuote = {
  legs: number;
  chance: number;
  decimal: number;
  estimated: boolean;
};
let slip: SlipQuote | null = null;
const slipListeners = new Set<() => void>();
const sameSlip = (a: SlipQuote | null, b: SlipQuote | null) =>
  a === b ||
  (!!a &&
    !!b &&
    a.legs === b.legs &&
    a.chance === b.chance &&
    a.decimal === b.decimal &&
    a.estimated === b.estimated);
export function setSlipQuote(q: SlipQuote | null) {
  if (sameSlip(slip, q)) return;
  slip = q;
  slipListeners.forEach((l) => l());
}
const subscribeSlip = (cb: () => void) => {
  slipListeners.add(cb);
  return () => {
    slipListeners.delete(cb);
  };
};

/** The stake for a slip, from the saved account and tonight's tracked bets. Null until a bankroll is set. */
export function stakeForSlip(
  q: SlipQuote,
  bets: Bet[],
  now = new Date(),
): Sizing | null {
  const account = readAccount();
  if (!account || account.bankroll <= 0) return null;
  // An estimated price is not a price the book has offered, so it is not sized.
  const price =
    q.estimated || !(q.decimal > 1) ? null : decimalToAmerican(q.decimal);
  return sizeBet(
    { prob: q.chance, price },
    account,
    tonightFrom(bets, now),
    now,
  );
}

// ---------- tracked bets, for pages that do not hold the bets store themselves ----------
const BETS_STORE = "godseye.bets.v1";
const NO_BETS: Bet[] = [];
let betsCache: Bet[] | null = null;
function readStoredBets(): Bet[] {
  if (betsCache === null) {
    try {
      const raw = JSON.parse(localStorage.getItem(BETS_STORE) ?? "[]");
      betsCache = Array.isArray(raw) ? (raw as Bet[]) : NO_BETS;
    } catch {
      betsCache = NO_BETS;
    }
  }
  return betsCache;
}
function subscribeStoredBets(cb: () => void) {
  const reload = () => {
    betsCache = null;
    cb();
  };
  window.addEventListener("ge-bets", reload);
  window.addEventListener("storage", reload);
  return () => {
    window.removeEventListener("ge-bets", reload);
    window.removeEventListener("storage", reload);
  };
}

/** One of the algorithm's own slips or singles, offered in the "size a pick" box. */
export type Pick = {
  id: string;
  label: string;
  chance: number;
  /** A real listed price, if there is one. Estimates are left out. */ price?:
    | number
    | null;
};

const parsePrice = (s: string) => {
  const n = Number(s.replace("−", "-").replace(/\s/g, ""));
  return Number.isFinite(n) && Math.abs(n) >= 100 ? n : null;
};

const usd = (n: number) => `$${Number.isInteger(n) ? n : n.toFixed(2)}`;
const signed = (n: number) =>
  `${n < 0 ? "−" : n > 0 ? "+" : ""}$${Math.abs(n).toFixed(2)}`;
const amount = (s: string) => {
  const n = Number(s.replace(/[$,\s]/g, ""));
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) / 100 : undefined;
};
const COOL_OFFS: [string, number][] = [
  ["24 hours", 24],
  ["3 days", 72],
  ["7 days", 168],
];

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
 * `bets`: the tracked bets, when the page already holds them (the NFL console). Left out, they are read from storage.
 * `picks`: the algorithm's slips for a page with no bet slip (NBA). Given, a "size a pick" box replaces the bet-slip box.
 */
export function BankrollStrategy({
  bets: given,
  picks,
}: {
  bets?: Bet[];
  picks?: Pick[];
}) {
  const stored = useSyncExternalStore(
    subscribeStoredBets,
    readStoredBets,
    () => NO_BETS,
  );
  const bets = given ?? stored;
  const [pickId, setPickId] = useState("");
  const [priceText, setPriceText] = useState<string | null>(null);
  const saved = useSyncExternalStore(subscribeAccount, readAccount, () => null);
  const quote = useSyncExternalStore(
    subscribeSlip,
    () => slip,
    () => null,
  );
  const [now] = useState(() => new Date());
  const [bankrollText, setBankrollText] = useState(() =>
    saved ? String(saved.bankroll) : "",
  );
  const [pendingCoolOff, setPendingCoolOff] = useState<number | null>(null);

  const account = saved ? withWeeklyUnit(saved, now) : null;
  const tonight = tonightFrom(bets, now);
  const limits = account ? checkLimits(account, tonight, now) : null;
  const terms = account ? termsOf(account) : null;
  const custom =
    account?.profile === "custom" ? clampCustom(account.custom) : null;
  const setCustom = (patch: Partial<CustomProfile>) =>
    account &&
    save({ custom: clampCustom({ ...clampCustom(account.custom), ...patch }) });
  const num = (text: string) => {
    const n = Number(text.replace(/[%u\s]/g, ""));
    return Number.isFinite(n) && n > 0 ? n : undefined;
  };
  const unit = account?.unit?.size ?? 0;
  const inUnits = (dollars: number) =>
    unit > 0 ? `${Math.round((dollars / unit) * 10) / 10}u` : "";

  const save = (patch: Partial<Account>) => {
    if (!account) return;
    writeAccount({ ...account, ...patch });
  };
  const setLimit = (patch: Partial<Limits>) =>
    account && save({ limits: { ...account.limits, ...patch } });
  const saveBankroll = () => {
    const n = amount(bankrollText);
    if (n === undefined) return;
    // First set-up fixes the unit. After that the unit holds until the new week (or a deliberate reset below).
    writeAccount(
      account ? { ...account, bankroll: n } : openAccount(n, "balanced", now),
    );
  };
  const coolOffActive =
    !!account?.limits.coolOffUntil &&
    new Date(account.limits.coolOffUntil).getTime() > now.getTime();
  const sizing = account && quote ? stakeForSlip(quote, bets, now) : null;
  const pick = picks?.find((x) => x.id === pickId) ?? picks?.[0] ?? null;
  const shownPrice =
    priceText ?? (pick?.price != null ? String(pick.price) : "");
  const pickPrice = parsePrice(shownPrice);
  const pickSizing =
    account && pick
      ? sizeBet({ prob: pick.chance, price: pickPrice }, account, tonight, now)
      : null;

  return (
    <>
      <section className="panel">
        <Head
          title="Bankroll Strategy"
          sub="Set what you are betting with and how hard you want to push it. Every stake on this site is sized from these settings. Bet smarter, survive the variance."
        />
        <div className="t-cols">
          <div>
            <label className="t-field">
              <span>
                Bankroll ($): money set aside for betting that you can afford to
                lose
              </span>
              <input
                inputMode="decimal"
                value={bankrollText}
                placeholder="1000"
                onChange={(e) => setBankrollText(e.target.value)}
                onBlur={saveBankroll}
                onKeyDown={(e) => e.key === "Enter" && saveBankroll()}
              />
            </label>
            {account && (
              <label className="t-field" style={{ marginTop: 12 }}>
                <span>Risk profile</span>
                <select
                  value={account.profile}
                  onChange={(e) => {
                    const profile = e.target.value as ProfileId;
                    save(
                      profile === "custom"
                        ? {
                            profile,
                            custom: clampCustom(
                              account.custom ?? CUSTOM_DEFAULT,
                            ),
                          }
                        : { profile },
                    );
                  }}
                >
                  {(Object.keys(PROFILES) as PresetId[]).map((id) => (
                    <option key={id} value={id}>
                      {PROFILES[id].label}: {PROFILES[id].blurb}
                    </option>
                  ))}
                  <option value="custom">
                    Custom: set your own unit size and limits.
                  </option>
                </select>
              </label>
            )}
            {account && custom && (
              // keyed on the saved values, so a number pulled back to its limit shows the value actually in force
              <div
                key={`${custom.unitPct}-${custom.maxBetUnits}-${custom.maxNightlyUnits}`}
              >
                <label className="t-field" style={{ marginTop: 12 }}>
                  <span>
                    Unit size (% of bankroll, {CUSTOM_BOUNDS.unitPct.min * 100}{" "}
                    to {CUSTOM_BOUNDS.unitPct.max * 100})
                  </span>
                  <input
                    inputMode="decimal"
                    defaultValue={Math.round(custom.unitPct * 10000) / 100}
                    onBlur={(e) => {
                      const n = num(e.target.value);
                      if (n !== undefined) setCustom({ unitPct: n / 100 });
                    }}
                  />
                </label>
                <label className="t-field" style={{ marginTop: 12 }}>
                  <span>
                    Most units on one bet (up to{" "}
                    {Math.round(
                      (CUSTOM_BOUNDS.maxBetPct / custom.unitPct) * 10,
                    ) / 10}
                    u, which is {CUSTOM_BOUNDS.maxBetPct * 100}% of bankroll)
                  </span>
                  <input
                    inputMode="decimal"
                    defaultValue={custom.maxBetUnits}
                    onBlur={(e) => {
                      const n = num(e.target.value);
                      if (n !== undefined) setCustom({ maxBetUnits: n });
                    }}
                  />
                </label>
                <label className="t-field" style={{ marginTop: 12 }}>
                  <span>
                    Most units in one night (up to{" "}
                    {Math.round(
                      (CUSTOM_BOUNDS.maxNightlyPct / custom.unitPct) * 10,
                    ) / 10}
                    u, which is {CUSTOM_BOUNDS.maxNightlyPct * 100}% of
                    bankroll)
                  </span>
                  <input
                    inputMode="decimal"
                    defaultValue={custom.maxNightlyUnits}
                    onBlur={(e) => {
                      const n = num(e.target.value);
                      if (n !== undefined) setCustom({ maxNightlyUnits: n });
                    }}
                  />
                </label>
              </div>
            )}
            {!account && (
              <div className="t-row">
                <button className="btn primary" onClick={saveBankroll}>
                  Set bankroll
                </button>
              </div>
            )}
          </div>
          {account && limits && terms && (
            <dl className="kv">
              <dt>One unit this week</dt>
              <dd>{usd(unit)}</dd>
              <dt>Most on one bet</dt>
              <dd>
                {usd(limits.maxBet)} <small>{inUnits(limits.maxBet)}</small>
              </dd>
              <dt>Most in one night</dt>
              <dd>
                {usd(limits.nightlyCap)}{" "}
                <small>{inUnits(limits.nightlyCap)}</small>
              </dd>
            </dl>
          )}
        </div>
        {account && (
          <p className="t-note">
            A unit is {Math.round((terms?.unitPct ?? 0.01) * 10000) / 100}% of
            your bankroll. It is set at the start of each week (Tuesday) and
            does not move after a win or a loss in between, so one bad night
            does not change how you bet the next.
            {unitFor(account.bankroll, terms?.unitPct) !== unit && (
              <>
                {" "}
                Your bankroll now gives a unit of{" "}
                {usd(unitFor(account.bankroll, terms?.unitPct))}; it takes over
                on Tuesday.{" "}
                <button
                  className="t-x"
                  onClick={() =>
                    save({
                      unit: {
                        size: unitFor(account.bankroll, terms?.unitPct),
                        weekOf: account.unit!.weekOf,
                        pct: terms?.unitPct,
                      },
                    })
                  }
                >
                  Use it now
                </button>
              </>
            )}
          </p>
        )}
      </section>

      {account && limits && (
        <>
          <section className="panel">
            <Head
              title="Tonight"
              sub="From the bets you have tracked since this morning."
            />
            <dl className="kv">
              <dt>Staked tonight</dt>
              <dd>
                {usd(tonight.staked)} of {usd(limits.nightlyCap)}
              </dd>
              <dt>Room left tonight</dt>
              <dd>{usd(limits.remaining)}</dd>
              <dt>Settled result tonight</dt>
              <dd
                className={
                  tonight.settledProfit > 0
                    ? "t-up"
                    : tonight.settledProfit < 0
                      ? "t-down"
                      : undefined
                }
              >
                {signed(tonight.settledProfit)}
              </dd>
            </dl>
            {limits.stop ? (
              <div className="warns">
                <div>{limits.message}</div>
              </div>
            ) : (
              <p className="sub">
                No limit has been reached. Stakes are being suggested.
              </p>
            )}
          </section>

          {picks && (
            <section className="panel">
              <Head
                title="Stake for a pick"
                sub="Choose one of tonight's algorithm picks and type the price your book is offering for it."
              />
              {!pick && (
                <p className="empty">No picks are posted for tonight yet.</p>
              )}
              {pick && pickSizing && (
                <>
                  <div className="t-cols">
                    <label className="t-field">
                      <span>Pick</span>
                      <select
                        value={pick.id}
                        onChange={(e) => {
                          setPickId(e.target.value);
                          setPriceText(null);
                        }}
                      >
                        {picks.map((x) => (
                          <option key={x.id} value={x.id}>
                            {x.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="t-field">
                      <span>Your book&apos;s price (American odds)</span>
                      <input
                        inputMode="text"
                        value={shownPrice}
                        placeholder="+250"
                        onChange={(e) => setPriceText(e.target.value)}
                      />
                    </label>
                  </div>
                  <p className="t-big" style={{ marginTop: 14 }}>
                    {pickSizing.status === "bet"
                      ? pickSizing.label
                      : pickSizing.status === "unrated"
                        ? "No stake yet"
                        : "No bet"}
                  </p>
                  <p className="sub">
                    Algorithm chance {(pick.chance * 100).toFixed(1)}%
                    {pickPrice != null &&
                      ` · price ${formatAmerican(pickPrice)}`}
                  </p>
                  <p className="sub">
                    {pickPrice == null
                      ? "Type the real price from your book. A same-game parlay is priced by the book as one bet, so use the price on your slip, not the leg prices multiplied."
                      : pickSizing.reason}
                  </p>
                </>
              )}
            </section>
          )}

          {!picks && (
            <section className="panel">
              <Head
                title="Stake for your bet slip"
                sub="Sized from the algorithm's chance and the price your book is offering."
              />
              {!quote && (
                <p className="empty">
                  Your bet slip is empty. Add picks from{" "}
                  <a href="#picks">Algorithm picks</a> or{" "}
                  <a href="#sgp">Game SGPs</a> and the stake appears here and on
                  the slip.
                </p>
              )}
              {quote && sizing && (
                <>
                  <p className="t-big">
                    {sizing.status === "bet"
                      ? sizing.label
                      : sizing.status === "unrated"
                        ? "No stake yet"
                        : "No bet"}
                  </p>
                  <p className="sub">
                    {quote.legs} leg{quote.legs > 1 ? "s" : ""} · algorithm
                    chance {(quote.chance * 100).toFixed(1)}%
                    {!quote.estimated &&
                      ` · price ${formatAmerican(decimalToAmerican(quote.decimal))}`}
                  </p>
                  <p className="sub">
                    {quote.estimated
                      ? "Type your book's real price on the bet slip. A stake is only sized against a price you can actually take."
                      : sizing.reason}
                  </p>
                </>
              )}
            </section>
          )}

          <section className="panel">
            <Head
              title="My limits"
              sub="Optional. Each one can only make the stakes stricter, and a limit that is reached ends the night."
            />
            <div className="t-cols">
              <div>
                <label className="t-field">
                  <span>Stop-loss ($ lost in one night)</span>
                  <input
                    inputMode="decimal"
                    defaultValue={account.limits.stopLoss ?? ""}
                    placeholder="none"
                    onBlur={(e) =>
                      setLimit({ stopLoss: amount(e.target.value) })
                    }
                  />
                </label>
                <label className="t-field" style={{ marginTop: 12 }}>
                  <span>Profit lock ($ won in one night)</span>
                  <input
                    inputMode="decimal"
                    defaultValue={account.limits.profitLock ?? ""}
                    placeholder="none"
                    onBlur={(e) =>
                      setLimit({ profitLock: amount(e.target.value) })
                    }
                  />
                </label>
                <label className="t-field" style={{ marginTop: 12 }}>
                  <span>My own nightly cap ($ staked in one night)</span>
                  <input
                    inputMode="decimal"
                    defaultValue={account.limits.nightlyCap ?? ""}
                    placeholder={`profile allows ${usd(Math.round(account.bankroll * (terms?.maxNightlyPct ?? 0) * 100) / 100)}`}
                    onBlur={(e) =>
                      setLimit({ nightlyCap: amount(e.target.value) })
                    }
                  />
                </label>
              </div>
              <div>
                <p className="sub" style={{ marginTop: 0 }}>
                  <b>Cool-off.</b> A break from stake suggestions. Once started
                  it cannot be ended early.
                </p>
                {coolOffActive ? (
                  <div className="warns">
                    <div>
                      Cool-off is on until{" "}
                      {new Date(account.limits.coolOffUntil!).toLocaleString(
                        "en-CA",
                        { dateStyle: "medium", timeStyle: "short" },
                      )}
                      .
                    </div>
                  </div>
                ) : (
                  <div className="t-row">
                    {COOL_OFFS.map(([label, hours]) => (
                      <button
                        key={hours}
                        className={
                          pendingCoolOff === hours ? "btn primary" : "btn"
                        }
                        onBlur={() => setPendingCoolOff(null)}
                        onClick={() => {
                          if (pendingCoolOff !== hours)
                            return setPendingCoolOff(hours);
                          setLimit({
                            coolOffUntil: new Date(
                              now.getTime() + hours * 3_600_000,
                            ).toISOString(),
                          });
                          setPendingCoolOff(null);
                        }}
                      >
                        {pendingCoolOff === hours ? `Confirm ${label}` : label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="panel">
            <Head title="How a stake is worked out" />
            <ul className="t-findings">
              <li>
                <span>
                  It starts from the algorithm&apos;s chance and the price on
                  offer. If the chance does not beat the price, the answer is no
                  bet.
                </span>
              </li>
              <li>
                <span>
                  When there is an edge, the stake is a quarter of what the
                  Kelly formula suggests. Quarter-Kelly gives up some growth to
                  make losing runs much shallower.
                </span>
              </li>
              <li>
                <span>
                  It is then held to your profile&apos;s most on one bet (
                  {usd(limits.maxBet)}) and to what is left of tonight&apos;s
                  cap, and rounded down to a tenth of a unit, for example{" "}
                  {formatStake(1.5, Math.round(1.5 * unit * 100) / 100)}.
                </span>
              </li>
              <li>
                <span>
                  A pick the algorithm has not rated gets no stake number.
                  Unrated means unrated.
                </span>
              </li>
            </ul>
          </section>
        </>
      )}
      <p className="t-note">
        Your bankroll settings are saved in this browser only. No stake is a
        promise: a well-sized bet still loses, and a parlay loses more often
        than it wins. If betting stops being fun, use cool-off, and free,
        confidential help is available in every province.
      </p>
    </>
  );
}
