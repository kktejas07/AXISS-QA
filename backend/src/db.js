import pg from "pg";
import { config } from "./config.js";

const { Pool } = pg;

export const pool = new Pool({
  connectionString: config.databaseUrl,
  ssl: config.databaseSsl ? { rejectUnauthorized: false } : undefined,
  max: Number(process.env.PG_POOL_MAX ?? 10),
  connectionTimeoutMillis: 10_000,
  idleTimeoutMillis: 30_000,
});

pool.on("error", (error) => {
  console.error("[db] idle client error:", error.message);
});

export async function query(text, params) {
  return pool.query(text, params);
}

export async function ping() {
  const { rows } = await pool.query("SELECT 1 AS ok");
  return rows[0]?.ok === 1;
}

export async function close() {
  await pool.end();
}
