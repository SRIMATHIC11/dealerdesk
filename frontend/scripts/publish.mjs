import { cp, mkdir, readdir, unlink, copyFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const assets = path.join(root, "portal/static/portal/assets");
const templates = path.join(root, "portal/templates/portal");
await mkdir(assets, { recursive: true });
await mkdir(templates, { recursive: true });
// Only remove previous generated asset files inside this dedicated output directory.
for (const entry of await readdir(assets, { withFileTypes: true })) {
  if (entry.isFile()) await unlink(path.join(assets, entry.name));
}
await cp(path.join(root, "frontend/dist/assets"), assets, { recursive: true });
await copyFile(
  path.join(root, "frontend/dist/index.html"),
  path.join(templates, "index.html"),
);
console.log(
  "Published compiled UI into portal/. Commit source and these serving assets together.",
);
