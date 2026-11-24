/**
 * Which user store this server uses: Postgres when DATABASE_URL is set, local files otherwise.
 */
import pg from "pg";
import { FileStore } from "./file.ts";
import { PgStore } from "./postgres.ts";
import type { UserStore } from "./types.ts";

/** A connection pool for DATABASE_URL. Hosted Postgres needs TLS; a database on this machine does not. */
export function openPool(url: string): pg.Pool {
  const local = /@(localhost|127\.0\.0\.1|\[::1\])[:/]/.test(url) || url.includes("host=/");
  return new pg.Pool({ connectionString: url, max: 5, ...(local ? {} : { ssl: true }) });
}

export function openStore(env: Record<string, string | undefined> = process.env): UserStore {
  return env.DATABASE_URL ? new PgStore(openPool(env.DATABASE_URL)) : new FileStore();
}
