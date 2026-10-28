import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { query, close } from "./db.js";

const schemaPath = fileURLToPath(new URL("./schema.sql", import.meta.url));

/**
 * Applies the idempotent schema. Safe to run on every boot.
 */
export async function migrate() {
  const sql = await readFile(schemaPath, "utf8");
  await query(sql);
  console.log("[db] schema is up to date");
}

/**
 * Retries the migration a few times so a cold database container can catch up.
 */
export async function migrateWithRetry({ attempts = 10, delayMs = 3_000 } = {}) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await migrate();
      return true;
    } catch (error) {
      const lastAttempt = attempt === attempts;
      console.error(
        `[db] migration attempt ${attempt}/${attempts} failed: ${error.message}`,
      );
      if (lastAttempt) return false;
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  return false;
}

const isDirectRun =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  migrate()
    .then(() => close())
    .then(() => process.exit(0))
    .catch(async (error) => {
      console.error("[db] migration failed:", error.message);
      await close().catch(() => {});
      process.exit(1);
    });
}
