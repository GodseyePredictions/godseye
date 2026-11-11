import Link from "next/link";

const bars = [
  { label: "Singles", roi: 4.2 },
  { label: "2-leg parlays", roi: -3.1 },
  { label: "3-leg parlays", roi: -11.4 },
  { label: "4+ leg parlays", roi: -22.0 },
  { label: "Player props", roi: 6.8 },
];

export default function Home() {
  return (
    <>
      <header className="wrap top">
        <Link href="/" className="brand">
          gods<span>eye</span>
        </Link>
        <nav aria-label="Main">
          <a href="#how" className="hide-sm">
            What it does
          </a>
          <a href="#pricing" className="hide-sm">
            Pricing
          </a>
          <Link href="/app" className="btn btn-primary btn-sm">
            Open the app
          </Link>
        </nav>
      </header>

      <main>
        <section className="wrap hero">
          <div>
            <h1 className="display">
              Check the slip <em>before you place it</em>
            </h1>
            <p className="lede">
              godseye is an AI advisor that reads your parlay or single, tells
              you what is wrong with it, and tracks how your bets really
              perform.
            </p>
            <div className="actions">
              <Link href="/app" className="btn btn-primary">
                Open the app
              </Link>
              <a href="#how" className="btn btn-ghost">
                See what it does
              </a>
            </div>
          </div>

          <div>
            <div className="slip" aria-label="Example bet slip reviewed by godseye">
              <div className="slip-head">
                <span>3-leg parlay</span>
                <small>Sunday NFL</small>
              </div>
              <div className="leg">
                <div className="leg-row">
                  <span>Bills −3.5</span>
                  <span className="num">−110</span>
                </div>
                <div className="leg-sub">Spread, Bills at Dolphins</div>
                <div className="note">
                  <b>Better line:</b> −3 at −112 on another book
                </div>
              </div>
              <div className="leg">
                <div className="leg-row">
                  <span>Josh Allen over 249.5 pass yds</span>
                  <span className="num">−115</span>
                </div>
                <div className="leg-sub">Player prop</div>
                <div className="note warn">
                  <b>Linked to leg 1:</b> these two win and lose together
                </div>
              </div>
              <div className="leg">
                <div className="leg-row">
                  <span>Chiefs moneyline</span>
                  <span className="num">−310</span>
                </div>
                <div className="leg-sub">Chiefs vs Raiders</div>
                <div className="note warn">
                  <b>Adds little:</b> big risk for a small bump in payout
                </div>
              </div>
              <div className="slip-foot">
                <span>$25 to win</span>
                <span className="num">$93.01</span>
              </div>
            </div>
            <p className="slip-caption">
              An illustration of an advisor review, not a real bet or a pick.
            </p>
          </div>
        </section>

        <section id="how" className="band band-deep">
          <div className="wrap">
            <h2 className="display">An advisor, not a tout</h2>
            <p className="intro">
              godseye does not sell locks. It helps you place the bets you
              already want to make at a better price, with fewer mistakes, and
              shows you the truth about your results.
            </p>
            <div className="jobs">
              <div>
                <h3>Talk through the slip</h3>
                <p>
                  Paste a slip or upload a screenshot. The advisor checks each
                  leg against odds across books and flags legs that are linked
                  or overpriced.
                </p>
              </div>
              <div>
                <h3>Track every bet</h3>
                <p>
                  Each slip you share is saved and settled. Singles, parlays
                  and props all land in one record of what you staked and what
                  came back.
                </p>
              </div>
              <div>
                <h3>Read your report</h3>
                <p>
                  See your return by sport, bet type and book, and whether you
                  are beating the closing line. The advisor uses it in every
                  chat.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="band">
          <div className="wrap report">
            <div>
              <h2 className="display">Find out where your money goes</h2>
              <p className="intro">
                Most bettors have never seen their own numbers. Your report
                breaks your history down so you can see which bets pay you and
                which ones pay the book.
              </p>
            </div>
            <div className="bars">
              <h3>Return by bet type</h3>
              <p>Example report with made-up numbers</p>
              {bars.map((b) => (
                <div className="bar-row" key={b.label}>
                  <span>{b.label}</span>
                  <span className="track">
                    <span
                      className={`fill ${b.roi >= 0 ? "up" : "down"}`}
                      style={{ width: `${Math.min(Math.abs(b.roi) * 2, 50)}%` }}
                    />
                  </span>
                  <span className={`num ${b.roi >= 0 ? "up-t" : "down-t"}`}>
                    {b.roi >= 0 ? "+" : "−"}
                    {Math.abs(b.roi).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="pricing" className="band band-deep">
          <div className="wrap">
            <h2 className="display">Start free. Go Pro when it helps.</h2>
            <div className="plans">
              <div className="plan">
                <h3>Free</h3>
                <div className="price">
                  $0
                </div>
                <ul>
                  <li>Track your bets from screenshots or pasted slips</li>
                  <li>Basic win and loss record</li>
                  <li>5 advisor chats each month</li>
                </ul>
                <Link href="/app" className="btn btn-ghost">
                  Open the app
                </Link>
              </div>
              <div className="plan pro">
                <h3>Pro</h3>
                <div className="price">
                  $29 <small>CAD per month</small>
                </div>
                <ul>
                  <li>Unlimited advisor chats</li>
                  <li>Full report by sport, bet type and book</li>
                  <li>Best-line check on every leg</li>
                  <li>Closing line tracking</li>
                </ul>
                <Link href="/app" className="btn">
                  Open the app
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="band">
          <div className="wrap">
            <h2 className="display">Straight talk</h2>
            <div className="straight">
              <p>
                <strong>godseye is not a sportsbook.</strong> You cannot place
                a bet here. You place bets with your own book and bring the
                slip to us.
              </p>
              <p>
                <strong>Nobody can promise you will win.</strong> Sportsbooks
                price in an edge, and most bettors lose over time. godseye
                helps you make fewer costly mistakes; it does not guarantee
                profit.
              </p>
              <p>
                <strong>NFL first.</strong> NBA is next.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="wrap">
          <p>
            For adults of legal betting age in their province (18+ or 19+).
            godseye provides information and analysis, not betting advice you
            should rely on for financial decisions.
          </p>
          <p>
            If gambling is causing you harm, free and confidential help is
            available in every province. Set a budget and never bet money you
            cannot afford to lose.
          </p>
        </div>
      </footer>
    </>
  );
}
