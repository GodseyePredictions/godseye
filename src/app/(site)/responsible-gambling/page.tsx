import type { Metadata } from "next";
import { ResponsibleGamblingPage } from "@/components/InfoPages";

export const metadata: Metadata = { title: "Responsible gambling", description: "The limits built into Godseye, warning signs, and where to get free, confidential help in Canada.", alternates: { canonical: "/responsible-gambling" } };

export default function Page() {
  return <ResponsibleGamblingPage />;
}
