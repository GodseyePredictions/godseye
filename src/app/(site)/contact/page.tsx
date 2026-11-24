import type { Metadata } from "next";
import { ContactPage } from "@/components/InfoPages";

export const metadata: Metadata = { title: "Contact", description: "How to reach Godseye Predictions.", alternates: { canonical: "/contact" } };

export default function Page() {
  return <ContactPage />;
}
