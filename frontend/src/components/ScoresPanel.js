import { actionableFailures, highestScore } from "../ui/helpers.js";

export function renderScoresPanel({ works, labels, helpers }) {
  const escapeHtml = helpers.escapeHtml;
  return `<section>
    <div class="section-title">
      <div>
        <h2>评分中心</h2>
        <p class="meta">按作品聚合评分，只显示可行动失败和建议动作。</p>
      </div>
    </div>
    <div class="table-panel">
      <table class="data-table">
        <thead><tr><th>作品名</th><th>最高分</th><th>最低分</th><th>候选数</th><th>失败原因 Top</th><th>建议动作</th><th>操作</th></tr></thead>
        <tbody>
          ${(works || []).map((work) => {
            const scores = (work.versions || []).map((version) => Number(version.score_total || 0));
            const failures = Array.from(new Set((work.versions || []).flatMap((version) => version.failure_codes || [])));
            const high = scores.length ? Math.max(...scores) : highestScore(work);
            const low = scores.length ? Math.min(...scores) : high;
            const action = failures.length ? "加入返工队列" : "标记通过";
            return `<tr data-work-id="${escapeHtml(work.work_id || "")}">
              <td>${escapeHtml(work.title || work.theme || "未命名作品")}</td>
              <td>${high || "-"}</td>
              <td>${low || "-"}</td>
              <td>${work.version_count || 0}</td>
              <td>${escapeHtml(actionableFailures(failures, labels.failureLabels))}</td>
              <td>${action}</td>
              <td class="table-actions">
                <button type="button" data-action="show-work-detail">查看候选</button>
                <button type="button" class="secondary" data-action="manual-rework">打回重构</button>
                <button type="button" class="secondary" data-action="mark-pass">标记通过</button>
                <button type="button" class="secondary" data-action="ignore-low-risk">忽略低风险提示</button>
              </td>
            </tr>`;
          }).join("") || `<tr><td colspan="7">暂无评分记录</td></tr>`}
        </tbody>
      </table>
    </div>
    <footer class="pagination-footer">第 1 页 / 每页 10 条</footer>
  </section>`;
}

export function renderReworkPanel({ works, labels, helpers }) {
  const escapeHtml = helpers.escapeHtml;
  const rows = (works || []).flatMap((work) => (work.versions || [])
    .filter((version) => (version.failure_codes || []).length || Number(version.score_total || 0) < 80)
    .map((version) => ({ work, version })));
  return `<section>
    <div class="section-title">
      <div>
        <h2>返工队列</h2>
        <p class="meta">按失败原因、风格、处理状态和时间筛选，可批量处理并指派责任 Agent。</p>
      </div>
    </div>
    <div class="filters">
      <div class="filter-grid compact">
        <div><label>失败原因</label><select><option>全部</option><option>结构过短</option><option>歌词太短</option><option>Hook 弱</option></select></div>
        <div><label>风格</label><select><option>全部</option><option>流行 Pop</option><option>电子 Electronic</option></select></div>
        <div><label>处理状态</label><select><option>待处理</option><option>处理中</option><option>已完成</option></select></div>
        <div><label>时间</label><input placeholder="2026-06-30"></div>
      </div>
    </div>
    <div class="bulk-bar">
      <button type="button" class="secondary" data-action="batch-rework">批量处理</button>
      <button type="button" class="secondary" data-action="assign-agent">指派责任 Agent</button>
    </div>
    <div class="table-panel">
      <table class="data-table">
        <thead><tr><th>来源作品</th><th>失败原因</th><th>风格</th><th>责任 Agent</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          ${rows.map(({ work, version }) => `<tr data-work-id="${escapeHtml(work.work_id || "")}" data-version-id="${escapeHtml(version.version_id || "")}">
            <td>${escapeHtml(work.title || work.theme || "未命名作品")}</td>
            <td>${escapeHtml(actionableFailures(version.failure_codes || [], labels.failureLabels))}</td>
            <td>${escapeHtml((work.genre || []).join("、") || "-")}</td>
            <td>返工调度 Agent</td>
            <td>待处理</td>
            <td class="table-actions">
              <button type="button" data-action="manual-rework">开始返工</button>
              <button type="button" class="secondary" data-action="regenerate-candidate">重新生成候选</button>
              <button type="button" class="secondary" data-action="edit-lyrics">改歌词</button>
              <button type="button" class="secondary" data-action="edit-arrangement">改编曲</button>
              <button type="button" class="secondary" data-action="edit-tone">改基调</button>
              <button type="button" class="secondary" data-action="mark-unhandled">标记无法处理</button>
            </td>
          </tr>`).join("") || `<tr><td colspan="6">暂无返工项</td></tr>`}
        </tbody>
      </table>
    </div>
    <footer class="pagination-footer">第 1 页 / 每页 10 条</footer>
  </section>`;
}
