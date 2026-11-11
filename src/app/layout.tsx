import type { Metadata } from "next";
import { Big_Shoulders, Figtree } from "next/font/google";
import "./globals.css";

const display = Big_Shoulders({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["700", "900"],
});

const body = Figtree({
  variable: "--font-body",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "godseye: check the slip before you place it",
  description:
    "An AI bet advisor and tracker for Canadian bettors. Review parlays and singles before you place them, and see how your own bets really perform.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-CA" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
