import { actionableFailures, formatDuration, labelOf } from "../ui/helpers.js";

export function renderWorkDetailDrawer(detail, labels, helpers) {
  const escapeHtml = helpers.escapeHtml;
  const selected = (detail.versions || []).find((item) => item.version_id === detail.selected_version_id) || (detail.versions || [])[0] || {};
  return `
    <div class="drawer-head">
      <div>
        <p class="meta">候选抽屉</p>
        <h2>${escapeHtml(detail.title || detail.theme || detail.work_id)}</h2>
      </div>
      <button type="button" class="secondary" data-action="close-work-detail">关闭</button>
    </div>
    <section class="detail-section">
      <h3>基础信息</h3>
      <dl class="detail-grid">
        ${item("标题", detail.title, escapeHtml)}
        ${item("主基调", (detail.mood || [])[0], escapeHtml)}
        ${item("风格", (detail.genre || []).map((genre) => labelOf(labels.genreLabels, genre)).join("、"), escapeHtml)}
        ${item("最高评分", detail.score_total, escapeHtml)}
        ${item("候选数", detail.version_count, escapeHtml)}
        ${item("是否成品", isFinished(detail) ? "是" : "否", escapeHtml)}
      </dl>
    </section>
    <section class="detail-section">
      <h3>候选版本</h3>
      <div class="candidate-list">
        ${(detail.versions || []).map((candidate, index) => renderCandidate(candidate, index, detail.selected_version_id, labels, helpers)).join("")}
      </div>
    </section>
    <section class="detail-section">
      <h3>歌词</h3>
      <pre>${escapeHtml(selected.lyrics || "暂无歌词")}</pre>
    </section>
    <section class="detail-section">
      <h3>评分与返工</h3>
      <p class="meta">失败原因: ${escapeHtml(actionableFailures(selected.failure_codes || [], labels.failureLabels))}</p>
      <div class="toolbar">
        <button type="button" data-action="manual-rework">打回返工</button>
        <button type="button" class="secondary" data-action="select-version">选择为最终版本</button>
        <button type="button" class="secondary" data-action="move-finished">移入成品库</button>
      </div>
    </section>
  `;
}

function renderCandidate(candidate, index, selectedId, labels, helpers) {
  const escapeHtml = helpers.escapeHtml;
  const name = ["钢琴抒情版", "电子氛围版", "鼓组增强版", "影视铺陈版", "原声清新版"][index] || `候选 ${index + 1}`;
  const selected = candidate.version_id === selectedId;
  const fullAudio = (candidate.export_files || []).find((file) => file.kind === "master" && file.path) || { path: candidate.audio_path };
  return `<article class="candidate-card ${selected ? "selected" : ""}" data-version-id="${escapeHtml(candidate.version_id || "")}">
    <div>
      <h4>${name}${selected ? " / 最终版本" : ""}</h4>
      <p class="meta">评分 ${candidate.score_total || "-"} / 完整版本 ${helpers.formatDuration(candidate.duration_sec || 180)}</p>
      <p class="meta">策略: ${escapeHtml(((candidate.generation_route || {}).candidate_strategy || {}).variation_type_zh || name)}</p>
    </div>
    ${fullAudio.path ? `<audio controls src="${helpers.fileUrl(fullAudio.path)}" aria-label="完整版本"></audio>` : ""}
    <div class="toolbar">
      <button type="button" data-action="play-candidate">播放完整版本</button>
      <button type="button" class="secondary" data-action="show-lyrics">查看歌词</button>
      <button type="button" class="secondary" data-action="select-version" ${selected ? "disabled" : ""}>选择为最终版本</button>
      <button type="button" class="secondary" data-action="manual-rework">打回返工</button>
      <button type="button" class="secondary" data-action="move-finished">移入成品库</button>
    </div>
  </article>`;
}

function item(label, value, escapeHtml) {
  return `<div><dt>${label}</dt><dd>${escapeHtml(String(value || "-"))}</dd></div>`;
}

function isFinished(detail) {
  return Number(detail.score_total || 0) >= 80 && !(detail.failure_codes || []).length && detail.selected_version_id;
}
