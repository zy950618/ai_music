export const fileUrl = (path) => path ? `/files?path=${encodeURIComponent(path)}` : "";

export const selectedList = (form, name) => form
  .getAll(name)
  .map((value) => String(value).trim())
  .filter(Boolean);

export const labelOf = (map, value) => map[value] || value || "-";

export const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>"']/g,
  (char) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char])
);

export function formatDuration(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

export function formatDate(value) {
  return value ? String(value).slice(0, 10) : "-";
}

export function highestScore(work) {
  return Math.max(...(work.versions || []).map((version) => Number(version.score_total || 0)), Number(work.score_total || 0));
}

export function actionableFailures(codes = [], labels = {}) {
  const mapped = (codes || []).map((code) => labelOf(labels, code));
  return mapped.length ? mapped.join("、") : "可通过";
}
