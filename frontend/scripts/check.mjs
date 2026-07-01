import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const src = resolve(root, "src");

const requiredFiles = [
  "index.html",
  "styles.css",
  "main.js",
  "app/AppShell.js",
  "components/AppHeader.js",
  "components/CreationPanel.js",
  "components/WorkspacePanel.js",
  "components/ScoresPanel.js",
  "components/WorksLibraryPanel.js",
  "components/WorkDetailDrawer.js",
  "components/DeliveryPanel.js",
  "controllers/creation-controller.js",
  "controllers/workbench-controller.js",
  "controllers/tabs-controller.js",
  "controllers/works-library-controller.js",
  "controllers/delivery-controller.js",
  "legacy/workbench-legacy.js",
  "services/workbench-api.js",
  "state/workbench-state.js",
  "ui/labels.js",
  "ui/helpers.js"
];

for (const file of requiredFiles) {
  if (!existsSync(resolve(src, file))) {
    throw new Error(`缺少前端源码文件: ${file}`);
  }
}

function listJsFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(dir, entry.name);
    if (entry.isDirectory()) return listJsFiles(path);
    return entry.name.endsWith(".js") ? [path] : [];
  });
}

const html = readFileSync(resolve(src, "index.html"), "utf8");
const css = readFileSync(resolve(src, "styles.css"), "utf8");
const jsFiles = listJsFiles(src);
const js = jsFiles.map((path) => readFileSync(path, "utf8")).join("\n");
const combined = `${html}\n${css}\n${js}`;

for (const term of ["MCP Broker", "No-Paid / Local-First", "Evidence Manifest", "research_only", "page_size=10", "lifecycle=active", "view_mode=card"]) {
  if (combined.includes(term)) {
    throw new Error(`普通前端源码出现禁止术语: ${term}`);
  }
}

for (const label of ["AI 音乐工坊", "选择用户工作库", "生产总览", "新建创作", "作品库", "成品库", "评分中心", "返工队列", "发布中心", "平台配置", "主基调", "副基调", "声音设计", "候选抽屉"]) {
  if (!combined.includes(label)) {
    throw new Error(`前端缺少 V5 文案: ${label}`);
  }
}

if (!html.includes('href="/static/workbench.css"')) {
  throw new Error("HTML 必须引用 /static/workbench.css");
}
if (!html.includes('src="/static/workbench.js"')) {
  throw new Error("HTML 必须引用 /static/workbench.js");
}
if (/<style[\s>]/i.test(html) || /<script(?![^>]*src=)[^>]*>/i.test(html)) {
  throw new Error("HTML 不允许内嵌 style/script");
}

for (const path of jsFiles) {
  const check = spawnSync(process.execPath, ["--check", path], { encoding: "utf8" });
  if (check.status !== 0) {
    throw new Error(`前端模块语法检查失败: ${path}\n${check.stderr || check.stdout}`);
  }
}

console.log("前端源码检查通过");
