import type { Metadata } from "next";
import { IBM_Plex_Sans, Saira_Condensed } from "next/font/google";
import { SITE } from "@/lib/site";
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
  metadataBase: new URL(SITE.url),
  title: { default: `${SITE.name}: see the whole slip before you bet it`, template: `%s | ${SITE.name}` },
  description: SITE.description,
  applicationName: SITE.name,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: SITE.name,
    title: `${SITE.name}: see the whole slip before you bet it`,
    description: SITE.description,
    url: "/",
    locale: "en_CA",
    images: [{ url: "/brand/banner.jpg", width: 1206, height: 214, alt: "The Godseye eye" }],
  },
  twitter: { card: "summary_large_image", title: SITE.name, description: SITE.description, images: ["/brand/banner.jpg"] },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-CA" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
