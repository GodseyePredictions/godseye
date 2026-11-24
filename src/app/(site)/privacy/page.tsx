import type { Metadata } from "next";
import { PrivacyPage } from "@/components/InfoPages";

export const metadata: Metadata = { title: "Privacy", description: "What Godseye collects, why, and what you can do about it.", alternates: { canonical: "/privacy" } };

export default function Page() {
  return <PrivacyPage />;
}
