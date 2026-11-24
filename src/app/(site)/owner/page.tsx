import type { Metadata } from "next";
import { Logo } from "@/components/Logo";
import { OwnerDashboard } from "@/components/OwnerDashboard";

export const metadata: Metadata = { title: "Owner", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <div className="lp">
      <header className="lp-nav">
        <div className="lp-wrap lp-nav-in">
          <Logo />
        </div>
      </header>
      <main id="content" className="lp-doc">
        <div className="lp-wrap">
          <h1>Owner</h1>
          <OwnerDashboard />
        </div>
      </main>
    </div>
  );
}
