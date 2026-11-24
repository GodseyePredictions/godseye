import type { ReactNode } from "react";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { ADVISOR_LIMITS } from "@/lib/advisor/subscription";
import { BETTING_AGE, HELPLINES, SITE } from "@/lib/site";
import { PROFILES } from "@/lib/staking";

/** Footer links shared by the landing page and the information pages. */
export const INFO_LINKS: [string, string][] = [
  ["/responsible-gambling", "Responsible gambling"],
  ["/terms", "Terms"],
  ["/privacy", "Privacy"],
  ["/contact", "Contact"],
];

export function SiteFooter({ children }: { children?: ReactNode }) {
  return (
    <footer className="lp-foot">
      <div className="lp-wrap lp-foot-in">
        <div>
          <Logo />
          <p>{SITE.tagline}</p>
        </div>
        <nav aria-label="Footer">
          {children}
          {INFO_LINKS.map(([href, label]) => (
            <Link key={href} href={href}>
              {label}
            </Link>
          ))}
        </nav>
        <p className="lp-legal">
          For adults of legal betting age in their province (18+ or 19+). Godseye provides information and analysis, not a promise of results.
          If gambling is causing you harm, free and confidential help is available in every province:{" "}
          <Link href="/responsible-gambling">where to get help</Link>. Set a budget and never bet money you cannot afford to lose.
        </p>
      </div>
    </footer>
  );
}

function Frame({ title, lede, children }: { title: string; lede: string; children: ReactNode }) {
  return (
    <div className="lp">
      <a className="lp-skip" href="#content">
        Skip to content
      </a>
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-in">
          <Logo />
          <nav aria-label="Main">
            <Link href="/">Home</Link>
            {INFO_LINKS.map(([href, label]) => (
              <Link key={href} href={href}>
                {label}
              </Link>
            ))}
          </nav>
          <div className="lp-sports" role="group" aria-label="Choose a sport">
            <Link href="/nfl">NFL</Link>
            <Link href="/nba">NBA</Link>
          </div>
        </div>
      </header>
      <main id="content" className="lp-doc">
        <div className="lp-wrap lp-doc-in">
          <h1>{title}</h1>
          <p className="lp-doc-lede">{lede}</p>
          {children}
          <p className="lp-doc-date">Last updated {SITE.legalUpdated}.</p>
        </div>
      </main>
      <SiteFooter>
        <Link href="/nfl">NFL</Link>
        <Link href="/nba">NBA</Link>
      </SiteFooter>
    </div>
  );
}

function ContactLine() {
  return SITE.contactEmail ? (
    <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>
  ) : (
    <span>our support address, which will be listed on the <Link href="/contact">contact page</Link> before subscriptions open</span>
  );
}

const pctOf = (x: number) => `${+(x * 100).toFixed(2)}%`;

export function ResponsibleGamblingPage() {
  return (
    <Frame
      title="Responsible gambling"
      lede="Godseye exists to help you make better-informed bets, and a better-informed bet can still lose. Most bettors lose money over time. Treat betting as paid entertainment, never as income."
    >
      <h2>What we will never tell you</h2>
      <ul>
        <li>That a pick is a sure thing or guaranteed. &ldquo;Algo Locks&rdquo; is our name for the algorithm&apos;s highest-chance slips, not a promise: every slip on this site shows its chance of losing next to its chance of winning.</li>
        <li>To chase a loss, raise your stake after a bad night, or bet more than your plan allows.</li>
        <li>That a number exists when the algorithm has not rated a leg. It is marked unrated and left at that.</li>
      </ul>

      <h2>The limits built into Godseye</h2>
      <p>These are in the Bankroll Strategy tab on both the NFL and NBA sides. You set them; the site and the advisor then hold you to them.</p>
      <ul>
        <li>
          <strong>Stake sizes you choose in advance.</strong> A risk profile caps each bet and each night:{" "}
          {Object.values(PROFILES).map((p, i, all) => (
            <span key={p.label}>
              {p.label} (at most {pctOf(p.maxBetPct)} of bankroll per bet, {pctOf(p.maxNightlyPct)} per night){i < all.length - 1 ? ", " : "."}
            </span>
          ))}
        </li>
        <li><strong>Unit size changes once a week,</strong> not after a loss, so one bad night cannot push your stakes up.</li>
        <li><strong>Stop-loss.</strong> Once you are down the amount you set for the night, no more stakes are suggested.</li>
        <li><strong>Profit lock.</strong> Once you are up the amount you set, the night is finished.</li>
        <li><strong>Nightly exposure cap.</strong> A ceiling on the total you can have at risk in one night.</li>
        <li><strong>Cool-off.</strong> A break you set that pauses stake suggestions until it ends.</li>
      </ul>

      <h2>Signs that betting has stopped being fun</h2>
      <ul>
        <li>Betting with money meant for rent, bills, food or debts.</li>
        <li>Raising stakes to win back what you lost.</li>
        <li>Hiding bets or losses from people close to you.</li>
        <li>Feeling anxious, irritable or low when you are not betting.</li>
        <li>Borrowing to bet.</li>
      </ul>
      <p>If any of these sound familiar, stop for now and talk to someone. The services below are free and confidential.</p>

      <h2>Where to get help</h2>
      <div className="lp-doc-table">
        <table>
          <thead>
            <tr>
              <th scope="col">Where you live</th>
              <th scope="col">Service</th>
              <th scope="col">Phone</th>
            </tr>
          </thead>
          <tbody>
            {HELPLINES.map((h) => (
              <tr key={h.where}>
                <th scope="row">{h.where}</th>
                <td>{h.name}</td>
                <td>
                  <a href={`tel:${h.phone.replace(/[^0-9]/g, "")}`}>{h.phone}</a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        If your province or territory is not listed, call 211 and ask for gambling support near you. Your sportsbook also has its own tools:
        deposit limits, time-outs and self-exclusion. Use them. If you are in immediate danger, call 911.
      </p>

      <h2>Legal age</h2>
      <p>You must be old enough to bet where you live. Godseye is not for anyone younger.</p>
      <ul>
        {BETTING_AGE.map((a) => (
          <li key={a.age}>
            <strong>{a.age}+:</strong> {a.where.join(", ")}.
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export function TermsPage() {
  const caps = ADVISOR_LIMITS.dailyMessages;
  return (
    <Frame title="Terms of use" lede="These terms cover your use of Godseye Predictions. By using the site you agree to them. If you do not agree, please do not use it.">
      <h2>1. What Godseye is</h2>
      <p>
        Godseye publishes the output of its own statistical models for NFL and NBA betting markets, and tools built on that output: slip audits,
        stake sizing and a chat advisor. It is information and analysis. Godseye is not a sportsbook, does not accept or place bets, and never
        holds your betting funds.
      </p>

      <h2>2. No promise of results</h2>
      <p>
        Probabilities, edges and suggested stakes are model estimates. They can be wrong, and a bet with a high estimated chance can still lose.
        Nothing on the site is a guarantee, and nothing is financial advice. You alone decide whether to place a bet and how much to stake, and
        you bear the result. Most bettors lose money over time.
      </p>

      <h2>3. Who can use it</h2>
      <p>
        You must be of legal betting age in your province or territory (18 or 19; see <Link href="/responsible-gambling">Responsible gambling</Link>)
        and betting on sports must be lawful where you are. You are responsible for following the laws that apply to you and the rules of any
        sportsbook you use.
      </p>

      <h2>4. Your account</h2>
      <p>Keep your sign-in details to yourself. One subscription is for one person. Tell us promptly if you think someone else has used your account.</p>

      <h2>5. Subscriptions and payment</h2>
      <ul>
        <li>Paid plans renew automatically each billing period until you cancel. The price is shown before you pay.</li>
        <li>You can cancel at any time. Access continues to the end of the period you have paid for.</li>
        <li>Payments are handled by our payment processor. We do not see or store your full card number.</li>
        <li>
          The advisor has a daily message allowance that depends on the plan: {caps.pro} messages a day on Pro
          {caps.elite === null ? ", no daily cap on Elite" : `, ${caps.elite} on Elite`}.
        </li>
        <li>
          If you cancel, your advisor history is kept for {ADVISOR_LIMITS.archiveDays} days in case you return, then deleted.
        </li>
      </ul>

      <h2>6. The advisor and the slip reader</h2>
      <p>
        The chat advisor and the screenshot reader use an AI model to read what you send and to explain results. Every probability, edge and
        stake they show comes from the Godseye algorithms and the staking engine, not from the AI model. The reader can misread a screenshot:
        you are shown what was read and asked to confirm it before anything is graded. Check it.
      </p>

      <h2>7. Fair use</h2>
      <ul>
        <li>Do not resell, republish or redistribute picks, model numbers or other content from the site.</li>
        <li>Do not scrape the site, share your account, or try to get around plan limits.</li>
        <li>Do not use the site to break the law or the rules of a sportsbook.</li>
      </ul>
      <p>We may suspend or close an account that breaks these terms.</p>

      <h2>8. Odds and third-party information</h2>
      <p>
        Prices, lines and availability belong to the sportsbooks and change without notice. A rung or price shown here may no longer be offered
        by the time you look. Always confirm the bet on your sportsbook before placing it. Godseye is not affiliated with any sportsbook, league
        or team; names are used only to identify markets.
      </p>

      <h2>9. Liability</h2>
      <p>
        The site is provided as it is. To the extent the law allows, Godseye is not liable for betting losses or for any indirect loss arising
        from your use of the site, and its total liability to you is limited to what you paid for your subscription in the three months before
        the claim. Nothing in these terms removes rights you have under consumer protection law.
      </p>

      <h2>10. Changes</h2>
      <p>We may update these terms. If a change is significant we will tell subscribers before it takes effect. Continuing to use the site after that means you accept the new terms.</p>

      <h2>11. Contact</h2>
      <p>Questions about these terms: <ContactLine />.</p>
    </Frame>
  );
}

export function PrivacyPage() {
  return (
    <Frame title="Privacy" lede="What Godseye collects, why, who else handles it, and what you can do about it. We collect what the product needs and nothing for advertising.">
      <h2>What we collect</h2>
      <ul>
        <li><strong>Account details:</strong> your email address and sign-in information, once accounts are open.</li>
        <li><strong>Betting settings you enter:</strong> bankroll, risk profile, limits, and the bets and slips you choose to track.</li>
        <li><strong>Slip screenshots and chat messages</strong> you send to the slip reader or the advisor, and the advisor&apos;s short running notes about your preferences.</li>
        <li><strong>Subscription status:</strong> your plan, its renewal date and whether it is active. Card details stay with the payment processor.</li>
        <li><strong>Usage records:</strong> how many advisor messages you send and what they cost us to process.</li>
      </ul>
      <p>We do not connect to your sportsbook account, and we do not ask for your sportsbook password.</p>

      <h2>Where it is kept</h2>
      <p>
        Until you sign in, your bankroll settings, tracked bets and saved slips are stored only in your own browser, on your device. Advisor
        conversations are stored on our servers so the advisor can remember context between chats.
      </p>

      <h2>What we use it for</h2>
      <ul>
        <li>To size stakes to your bankroll and limits, and to audit the slips you send.</li>
        <li>To let the advisor answer with your own history in view.</li>
        <li>To run your subscription and enforce plan limits.</li>
        <li>To keep the service secure and to measure what it costs to run.</li>
      </ul>
      <p>We do not sell your information, and we do not use it for advertising.</p>

      <h2>Who else handles it</h2>
      <ul>
        <li><strong>Anthropic</strong> processes the screenshots and chat messages you send, to read slips and write replies.</li>
        <li><strong>Our payment processor</strong> handles card payments and tells us your subscription status.</li>
        <li><strong>Our hosting, sign-in and database providers</strong> store and serve the site and your account.</li>
      </ul>
      <p>These companies process information on our behalf and may do so outside Canada.</p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Account and betting records: for as long as your account is open.</li>
        <li>Advisor history: until you clear it, or {ADVISOR_LIMITS.archiveDays} days after you cancel.</li>
        <li>Screenshots: used to read the slip and not kept afterwards.</li>
      </ul>

      <h2>Your choices</h2>
      <ul>
        <li>View and clear your advisor history and its notes from the History button in the chat.</li>
        <li>Remove tracked bets and saved slips from their tabs at any time.</li>
        <li>Ask us for a copy of your information, to correct it, or to delete your account: <ContactLine />.</li>
      </ul>

      <h2>Cookies and browser storage</h2>
      <p>The site uses browser storage to remember your settings and to keep you signed in. It does not use advertising or cross-site tracking cookies.</p>

      <h2>Changes</h2>
      <p>If this policy changes in a way that matters, we will tell subscribers before the change takes effect.</p>
    </Frame>
  );
}

export function ContactPage() {
  return (
    <Frame title="Contact" lede="Questions about a pick, your subscription or your account.">
      <h2>Support</h2>
      {SITE.contactEmail ? (
        <p>
          Write to <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a>. Include the email address on your account and, for a pick or
          slip question, the game and the legs.
        </p>
      ) : (
        <p>Our support address is being set up and will be listed here before subscriptions open.</p>
      )}

      <h2>Quick answers</h2>
      <ul>
        <li><strong>A number looks wrong.</strong> Tell us the game, the player and the market. Every figure comes from the algorithm, so we can trace it.</li>
        <li><strong>A leg says unrated.</strong> The algorithm does not cover that market or player, so no number is shown. That is deliberate.</li>
        <li><strong>The price on my book is different.</strong> Books move prices constantly. Type the price you actually see and the stake is resized to it.</li>
        <li><strong>I want to cancel.</strong> You can cancel at any time; access runs to the end of the period you paid for.</li>
      </ul>

      <h2>If betting is causing you harm</h2>
      <p>
        Please do not wait for a reply from us. Free, confidential help is listed on the <Link href="/responsible-gambling">Responsible gambling</Link> page.
      </p>
    </Frame>
  );
}
