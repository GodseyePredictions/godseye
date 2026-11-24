/**
 * Facts about the business that the public pages print. Edit here, not in the pages.
 */
export const SITE = {
  name: "Godseye Predictions",
  tagline: "Bet smarter, survive the variance.",
  description:
    "Algorithm picks, same-game parlay audits, bankroll sizing and a personal advisor for NFL and NBA bettors. Every slip shows its chance of winning and of losing before you place it.",
  /** The public address of the site, for share previews and the sitemap. Set NEXT_PUBLIC_SITE_URL when hosted. */
  url: (typeof process !== "undefined" && process.env.NEXT_PUBLIC_SITE_URL) || "http://localhost:3000",
  /** Where users write to. Empty until the owner sets one: the pages then say the address is coming. */
  contactEmail: "",
  /** Shown on the legal pages. Change when their wording changes. */
  legalUpdated: "24 November 2026",
};

/** Minimum age to bet, by province or territory. Check against each regulator before launch. */
export const BETTING_AGE: { age: 18 | 19; where: string[] }[] = [
  { age: 18, where: ["Alberta", "Manitoba", "Quebec"] },
  { age: 19, where: ["British Columbia", "New Brunswick", "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia", "Nunavut", "Ontario", "Prince Edward Island", "Saskatchewan", "Yukon"] },
];

/**
 * Free, confidential gambling help lines. Only lines whose number was confirmed are listed;
 * anywhere else in Canada, 211 connects to local services. Check every number before launch.
 */
export const HELPLINES: { where: string; name: string; phone: string }[] = [
  { where: "Anywhere in Canada", name: "211 (community and health services)", phone: "211" },
  { where: "Alberta", name: "Addiction Helpline", phone: "1-866-332-2322" },
  { where: "British Columbia", name: "Gambling Support Line", phone: "1-888-795-6111" },
  { where: "Manitoba", name: "Problem Gambling Helpline", phone: "1-800-463-1554" },
  { where: "Ontario", name: "ConnexOntario", phone: "1-866-531-2600" },
  { where: "Saskatchewan", name: "Problem Gambling Helpline", phone: "1-800-306-6789" },
];
