import Link from "next/link";

export const metadata = { title: "Accounts open soon | godseye" };

export default function SignUp() {
  return (
    <main className="wrap simple">
      <Link href="/" className="brand">
        gods<span>eye</span>
      </Link>
      <h1 className="display">Accounts open soon</h1>
      <p>
        godseye is still being built, so you cannot create an account yet.
        Sign-up will open on this page at launch.
      </p>
      <div>
        <Link href="/" className="btn btn-ghost">
          Back to home
        </Link>
      </div>
    </main>
  );
}
