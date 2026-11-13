/**
 * Writes each illustration in src/components/Illustrations.tsx to
 * public/illustrations/<name>.svg, so the same art can be used outside the app
 * (emails, docs, slides). Run with `npm run illustrations` after changing one.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import * as art from "../src/components/Illustrations";

const { EmptyPanel: _panel, ...pictures } = art;
const kebab = (name: string) => name.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase();

mkdirSync("public/illustrations", { recursive: true });
for (const [name, Picture] of Object.entries(pictures)) {
  const svg = renderToStaticMarkup(<Picture />)
    .replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ')
    .replace(/ class="[^"]*"/, ' width="240" height="180"')
    .replace(/ (role|aria-hidden)="[^"]*"/g, "");
  writeFileSync(`public/illustrations/${kebab(name)}.svg`, svg + "\n");
  console.log(`public/illustrations/${kebab(name)}.svg`);
}
