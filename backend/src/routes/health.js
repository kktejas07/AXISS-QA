import { Router } from "express";
import { ping } from "../db.js";

export const healthRouter = Router();

healthRouter.get("/health", async (_req, res) => {
  let db = "down";

  try {
    if (await ping()) db = "up";
  } catch (error) {
    console.error("[api] health check db error:", error.message);
  }

  const healthy = db === "up";

  res.status(healthy ? 200 : 503).json({
    status: healthy ? "ok" : "degraded",
    db,
    uptime: Math.round(process.uptime()),
    timestamp: new Date().toISOString(),
  });
});
