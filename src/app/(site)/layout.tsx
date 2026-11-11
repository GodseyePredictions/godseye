import type { Metadata } from "next";
import { IBM_Plex_Sans, Saira_Condensed } from "next/font/google";
import "./globals.css";

const display = Saira_Condensed({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["700", "800"],
});

const body = IBM_Plex_Sans({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "godseye predictions: check the slip before you place it",
  description:
    "NFL model picks, a same-game parlay builder, slip audits and a tracker for Canadian bettors. See the model's number for every leg and how your own bets really perform.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-CA" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
