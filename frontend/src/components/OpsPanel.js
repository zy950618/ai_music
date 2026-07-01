export function renderOpsPanel(opsState = {}) {
  return `<div class="metric-grid">
    <article class="metric"><span>任务</span><strong>${opsState.task_count || 0}</strong></article>
    <article class="metric"><span>版本</span><strong>${opsState.version_count || 0}</strong></article>
    <article class="metric"><span>待返工</span><strong>${(opsState.rework || {}).queued || 0}</strong></article>
    <article class="metric"><span>平均分</span><strong>${(opsState.quality || {}).average_score || 0}</strong></article>
  </div>`;
}
