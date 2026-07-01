import { copyFileSync, cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import "./check.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(root, "..");
const src = resolve(root, "src");
const out = resolve(projectRoot, "music_ai", "static");

mkdirSync(out, { recursive: true });
copyFileSync(resolve(src, "styles.css"), resolve(out, "workbench.css"));
copyFileSync(resolve(src, "main.js"), resolve(out, "workbench.js"));
for (const dir of ["app", "components", "controllers", "legacy", "services", "state", "ui"]) {
  rmSync(resolve(out, dir), { recursive: true, force: true });
  cpSync(resolve(src, dir), resolve(out, dir), { recursive: true });
}

const html = readFileSync(resolve(src, "index.html"), "utf8");
writeFileSync(resolve(out, "workbench.html"), html, "utf8");

console.log("前端构建完成：music_ai/static/workbench.html, workbench.css, workbench.js");
