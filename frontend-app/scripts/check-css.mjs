// Fails the build when a stylesheet has unbalanced braces. Browsers silently drop every rule after an
// unclosed "{", and Vite's build does not report it, so a merge that loses a "}" would otherwise
// ship half the styles (it happened once: PR #102's conflict resolution).
// Usage: node scripts/check-css.mjs  (runs as part of `npm run build`)
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

function cssFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return cssFiles(path);
    return entry.name.endsWith(".css") ? [path] : [];
  });
}

let failed = false;
for (const file of cssFiles(root)) {
  // Ignore braces inside comments and strings.
  const text = readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, '""');
  let depth = 0;
  let line = 1;
  for (const ch of text) {
    if (ch === "\n") line += 1;
    else if (ch === "{") depth += 1;
    else if (ch === "}") {
      depth -= 1;
      if (depth < 0) {
        console.error(`${file}: unexpected "}" near line ${line}`);
        failed = true;
        break;
      }
    }
  }
  if (depth > 0) {
    console.error(`${file}: ${depth} unclosed "{" (a rule is missing its closing brace)`);
    failed = true;
  }
}

if (failed) process.exit(1);
console.log("CSS braces balanced");
