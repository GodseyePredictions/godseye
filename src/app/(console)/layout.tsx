import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Saira_Condensed } from "next/font/google";
import "./console.css";

const display = Saira_Condensed({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "700", "800"],
});
const body = IBM_Plex_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const mono = IBM_Plex_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "godseye predictions",
  description:
    "NFL model picks, same-game parlay builder, slip audit, and a tracker for your own bets.",
};

export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-CA" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
