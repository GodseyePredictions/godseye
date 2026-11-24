/**
 * Create or update the database tables from db/schema.sql. Needs DATABASE_URL. Safe to run again.
 *
 *   DATABASE_URL=postgres://... npm run db:migrate
 */
import { readFileSync } from "node:fs";
import { openPool } from "../src/lib/store/open.ts";

const url = process.env.DATABASE_URL;
if (!url) {
  console.error("Set DATABASE_URL to the Postgres connection string first.");
  process.exit(1);
}
const pool = openPool(url);
try {
  await pool.query(readFileSync(new URL("../db/schema.sql", import.meta.url), "utf8"));
  const { rows } = await pool.query("select table_name from information_schema.tables where table_schema = current_schema() order by 1");
  console.log("Tables:", rows.map((r) => r.table_name).join(", "));
} finally {
  await pool.end();
}
