import type { Metadata } from "next";
import { TermsPage } from "@/components/InfoPages";

export const metadata: Metadata = { title: "Terms of use", description: "The terms that cover your use of Godseye Predictions.", alternates: { canonical: "/terms" } };

export default function Page() {
  return <TermsPage />;
}
