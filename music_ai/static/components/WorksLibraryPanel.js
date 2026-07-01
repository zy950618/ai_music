import { actionableFailures, formatDate, highestScore, labelOf } from "../ui/helpers.js";

export function renderWorksLibrary({ worksState, workFilters, labels, helpers }) {
  const pagination = worksState.pagination || { page: 1, page_size: 10, total: 0, page_count: 0 };
  const items = worksState.items || [];
  const escapeHtml = helpers.escapeHtml;
  return `
    <section class="library-toolbar">
      <div class="section-title">
        <div>
          <h2>作品库</h2>
          <p class="meta">按作品管理候选，候选只在右侧抽屉中查看和处理。</p>
        </div>
      </div>
      <form id="workFilters" class="filters auto-filters">
        <div class="filter-grid compact">
          <div><label>关键词</label><input name="q" value="${escapeHtml(workFilters.q || "")}" placeholder="标题或主题"></div>
          <div><label>创作时间起</label><input name="generated_from" value="${escapeHtml(workFilters.generated_from || "")}" placeholder="2026-06-30"></div>
          <div><label>创作时间止</label><input name="generated_to" value="${escapeHtml(workFilters.generated_to || "")}" placeholder="2026-06-30"></div>
          <div><label>归档/删除状态</label><select name="lifecycle">${option("", "有效作品", workFilters.lifecycle)}${option("archived", "已归档", workFilters.lifecycle)}${option("deleted", "已删除", workFilters.lifecycle)}</select></div>
          <div><label>排序</label><select name="sort">${option("generatedAt:desc", "创作时间降序", workFilters.sort)}${option("score_total:desc", "最高评分降序", workFilters.sort)}${option("title:asc", "标题升序", workFilters.sort)}</select></div>
          <div><label>每页数量</label><select name="page_size">${option("10", "10", String(workFilters.page_size || 10))}${option("20", "20", String(workFilters.page_size || 10))}${option("50", "50", String(workFilters.page_size || 10))}</select></div>
        </div>
        <details class="advanced-filters">
          <summary>高级筛选</summary>
          <div class="filter-grid compact">
            <div><label>分类</label><input name="category" value="${escapeHtml(workFilters.category || "")}"></div>
            <div><label>主基调</label><input name="mood" value="${escapeHtml(workFilters.mood || "")}"></div>
            <div><label>风格</label><input name="genre" value="${escapeHtml(workFilters.genre || "")}"></div>
            <div><label>最低评分</label><input name="min_score" type="number" min="0" max="100" value="${escapeHtml(workFilters.min_score || "")}"></div>
            <div><label>是否成品</label><select name="finished">${option("", "全部", workFilters.finished)}${option("true", "已移入成品库", workFilters.finished)}${option("false", "未移入成品库", workFilters.finished)}</select></div>
          </div>
        </details>
      </form>
      <div id="bulkBar" class="bulk-bar hidden">
        <span id="bulkCount">已选择 0 个作品</span>
        <button type="button" class="secondary" data-action="bulk-archive">批量归档</button>
        <button type="button" class="secondary danger" data-action="bulk-delete">批量删除</button>
      </div>
    </section>
    <div class="work-card-grid">
      ${items.length ? items.map((item) => renderWorkCard(item, labels, helpers)).join("") : `<article class="empty-state"><h3>暂无作品</h3><p class="meta">调整筛选条件或新建创作。</p></article>`}
    </div>
    <footer class="pagination-footer">
      <button type="button" class="secondary" data-action="prev-work-page" ${pagination.page <= 1 ? "disabled" : ""}>上一页</button>
      <span>第 ${pagination.page || 1} 页 / 共 ${pagination.page_count || 0} 页，总数 ${pagination.total || 0}，每页 ${pagination.page_size || 10}</span>
      <button type="button" class="secondary" data-action="next-work-page" ${pagination.page >= pagination.page_count ? "disabled" : ""}>下一页</button>
    </footer>
    <div id="workDetailDrawer" class="drawer hidden"></div>
  `;
}

export function renderFinishedLibrary({ worksState, labels, helpers }) {
  const finished = (worksState.items || []).filter((item) => isFinished(item));
  return `<section>
    <div class="section-title"><div><h2>成品库</h2><p class="meta">只展示已选最终候选、评分合格、无硬性失败的作品。</p></div></div>
    <div class="work-card-grid">
      ${finished.length ? finished.map((item) => renderFinishedCard(item, labels, helpers)).join("") : `<article class="empty-state"><h3>暂无成品</h3><p class="meta">在作品库选择候选后移入成品库。</p></article>`}
    </div>
  </section>`;
}

function renderWorkCard(item, labels, helpers) {
  const escapeHtml = helpers.escapeHtml;
  const selected = item.selected_version || {};
  const isDone = isFinished(item);
  const score = highestScore(item);
  return `<article class="work-card" data-work-id="${escapeHtml(item.work_id || "")}" data-task-id="${escapeHtml(item.task_id || "")}" data-version-id="${escapeHtml(item.selected_version_id || "")}">
    <label class="select-corner" title="选择作品">
      <input type="checkbox" data-role="work-select" value="${escapeHtml(item.work_id || "")}">
      <span>✓</span>
    </label>
    <div class="card-body">
      <h3>${escapeHtml(item.title || item.theme || "未命名作品")}</h3>
      <div class="compact-lines">
        <span>主基调 ${escapeHtml((item.mood || [])[0] || "-")}</span>
        <span>风格 ${(item.genre || []).map((genre) => escapeHtml(labelOf(labels.genreLabels, genre))).join("、") || "-"}</span>
        <span>最高评分 ${score || "-"}</span>
        <span>创作时间 ${formatDate(item.generatedAt || item.createdAt)}</span>
        <span>候选数 ${item.version_count || 0}</span>
        <span>${isDone ? "已入成品库" : "未入成品库"}</span>
      </div>
      <div class="status-row">
        <span class="status ${score >= 80 ? "good" : "warn"}">${score >= 80 ? "评分通过" : "需要返工"}</span>
        <span class="status">${lifecycleLabel(item.lifecycle_status)}</span>
      </div>
      <div class="toolbar card-actions">
        <button type="button" data-action="show-work-detail">查看候选</button>
        <button type="button" class="secondary" data-action="move-finished">移入成品库</button>
      </div>
    </div>
  </article>`;
}

function renderFinishedCard(item, labels, helpers) {
  const escapeHtml = helpers.escapeHtml;
  const selected = item.selected_version || {};
  return `<article class="work-card finished-card" data-work-id="${escapeHtml(item.work_id || "")}" data-task-id="${escapeHtml(item.task_id || "")}" data-version-id="${escapeHtml(item.selected_version_id || "")}">
    <h3>${escapeHtml(item.title || item.theme || "未命名成品")}</h3>
    <p class="meta">最终版本: ${escapeHtml(selected.title || "已选候选")} / 评分 ${highestScore(item)}</p>
    <p class="meta">完整版本 ${helpers.formatDuration(selected.duration_sec || item.full_duration_sec || 180)}</p>
    <div class="toolbar">
      <button type="button" data-action="show-work-detail">查看候选</button>
      <button type="button" data-action="publish-work">发布</button>
      <button type="button" class="secondary" data-action="remove-finished">移出成品库</button>
    </div>
  </article>`;
}

function isFinished(item) {
  const score = highestScore(item);
  const failures = item.failure_codes || [];
  return score >= 80 && failures.length === 0 && item.selected_version_id;
}

function lifecycleLabel(value) {
  return { active: "有效作品", archived: "已归档", deleted: "已删除" }[value] || "有效作品";
}

function option(value, label, current) {
  return `<option value="${value}" ${String(current || "") === value ? "selected" : ""}>${label}</option>`;
}
