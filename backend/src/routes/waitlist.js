import { Router } from "express";
import { query } from "../db.js";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const MAX_EMAIL_LENGTH = 254;

export const waitlistRouter = Router();

waitlistRouter.post("/waitlist", async (req, res) => {
  const email = String(req.body?.email ?? "").trim().toLowerCase();
  const source = String(req.body?.source ?? "coming-soon").slice(0, 64);

  if (!EMAIL_PATTERN.test(email) || email.length > MAX_EMAIL_LENGTH) {
    return res.status(400).json({
      error: "Please enter a valid email address.",
    });
  }

  const { rows } = await query(
    `INSERT INTO waitlist (email, source)
     VALUES ($1, $2)
     ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email
     RETURNING (xmax = 0) AS inserted, created_at`,
    [email, source],
  );

  const inserted = Boolean(rows[0]?.inserted);

  return res.status(inserted ? 201 : 200).json({
    ok: true,
    email,
    alreadyRegistered: !inserted,
    message: inserted
      ? "You're on the list. We'll be in touch soon."
      : "You're already on the list. Thanks for the enthusiasm!",
  });
});

waitlistRouter.get("/waitlist/count", async (_req, res) => {
  const { rows } = await query("SELECT COUNT(*)::int AS count FROM waitlist");
  res.json({ count: rows[0]?.count ?? 0 });
});
