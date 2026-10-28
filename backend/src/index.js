import express from "express";
import cors from "cors";
import { config } from "./config.js";
import { close } from "./db.js";
import { migrateWithRetry } from "./migrate.js";
import { healthRouter } from "./routes/health.js";
import { waitlistRouter } from "./routes/waitlist.js";

const app = express();

app.disable("x-powered-by");

app.use(
  cors({
    origin:
      config.corsOrigin === "*"
        ? true
        : config.corsOrigin.split(",").map((origin) => origin.trim()),
  }),
);
app.use(express.json({ limit: "32kb" }));

app.get("/", (_req, res) => {
  res.json({
    name: "AXISS QA API",
    status: "coming-soon",
    docs: ["GET /api/health", "POST /api/waitlist", "GET /api/waitlist/count"],
  });
});

app.use("/api", healthRouter);
app.use("/api", waitlistRouter);

app.use((_req, res) => {
  res.status(404).json({ error: "Not found" });
});

// Express 5 forwards rejected promises from handlers here.
app.use((error, _req, res, _next) => {
  console.error("[api] unhandled error:", error);
  res.status(500).json({ error: "Something went wrong. Please try again." });
});

const server = app.listen(config.port, "0.0.0.0", () => {
  console.log(`[api] listening on http://0.0.0.0:${config.port}`);
});

// Warm the database up in the background: the API stays available either way,
// and /api/health reports whether the database is actually reachable.
migrateWithRetry().then((ok) => {
  if (ok) {
    console.log("[api] database ready");
  } else {
    console.error("[api] starting without a reachable database");
  }
});

let shuttingDown = false;

async function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`[api] received ${signal}, shutting down`);

  server.close(async () => {
    await close().catch(() => {});
    process.exit(0);
  });

  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
