#!/usr/bin/env node
/**
 * Installs the animated Wise character from the "Agent Pals" Lottie pack.
 *
 *   node scripts/install-wise-bot.mjs "<path to>/Lottie Pack/Circle"            brand colours
 *   node scripts/install-wise-bot.mjs "<path to>/Lottie Pack/Circle" --original  the pack's own colours
 *
 * The pack is licensed artwork, so its files are NOT in this repository: public/wise-bot/ is git-ignored.
 * Run this once on each machine that builds the web app (before `npm run build`). Without it, Wise shows
 * the drawn owl instead and everything else works the same.
 */
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const [source, flag] = process.argv.slice(2);
if (!source) {
  console.error('Give the folder of one bot, for example: node scripts/install-wise-bot.mjs "Agent Pals/Lottie Pack/Circle"');
  process.exit(1);
}
const STATES = ["Idle", "Working", "Typing", "Thinking", "Reading", "Writing", "Designing", "Coding", "Searching", "Listening", "Sleeping", "Done", "Error"];
// The bot's own two body colours, read from its Idle file, are swapped for Wiseflow's indigo.
const BRAND = { deep: [0x1e, 0x1b, 0x4b], bright: [0x63, 0x66, 0xf1] };
const near = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 0.004);

function bodyColours(idle) {
  let found = null;
  const walk = (o) => {
    if (found || !o || typeof o !== "object") return;
    if (!Array.isArray(o) && o.ty === "gf" && typeof o.g?.k?.k?.[0] === "number") {
      // The body is the first gradient: its darkest stop is the deep colour, its lightest the bright one.
      const stops = Array.from({ length: o.g.p }, (_, i) => o.g.k.k.slice(i * 4 + 1, i * 4 + 4));
      const light = (c) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
      stops.sort((a, b) => light(a) - light(b));
      found = { deep: stops[0], bright: stops[stops.length - 1] };
      return;
    }
    for (const v of Array.isArray(o) ? o : Object.values(o)) walk(v);
  };
  walk(idle);
  if (!found) throw new Error("Could not find the bot's body colours in Idle.json");
  return found;
}

function recolour(node, from) {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node)) return node.forEach((n) => recolour(n, from));
  const swap = (rgb) => {
    for (const key of ["deep", "bright"]) if (near(rgb, from[key])) return BRAND[key].map((v) => v / 255);
    return null;
  };
  if ((node.ty === "fl" || node.ty === "st") && typeof node.c?.k?.[0] === "number") {
    const to = swap(node.c.k.slice(0, 3));
    if (to) node.c.k.splice(0, 3, ...to);
  }
  if ((node.ty === "gf" || node.ty === "gs") && typeof node.g?.k?.k?.[0] === "number") {
    const k = node.g.k.k;
    for (let i = 0; i < node.g.p; i++) {
      const to = swap(k.slice(i * 4 + 1, i * 4 + 4));
      if (to) k.splice(i * 4 + 1, 3, ...to);
    }
  }
  Object.values(node).forEach((v) => recolour(v, from));
}

const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "wise-bot");
mkdirSync(out, { recursive: true });
const files = readdirSync(source);
const from = bodyColours(JSON.parse(readFileSync(join(source, files.find((f) => /idle\.json$/i.test(f))), "utf8")));
for (const state of STATES) {
  const file = files.find((f) => new RegExp(`(^|[ -])${state}\\.json$`, "i").test(f));
  if (!file) throw new Error(`${state}.json is missing from ${source}`);
  const data = JSON.parse(readFileSync(join(source, file), "utf8"));
  if (flag !== "--original") recolour(data, from);
  writeFileSync(join(out, `${state.toLowerCase()}.json`), JSON.stringify(data));
}
console.log(`Installed ${STATES.length} animations in public/wise-bot (${flag === "--original" ? "original colours" : "Wiseflow indigo"}).`);
