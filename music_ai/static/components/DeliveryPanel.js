import { highestScore } from "../ui/helpers.js";

const platforms = ["抖音", "快手", "视频号", "B站", "小红书", "网易云", "QQ音乐", "酷狗", "YouTube", "TikTok", "自定义平台"];

export function renderPublishCenter({ works, publishTasks, platformConfigs, helpers }) {
  const escapeHtml = helpers.escapeHtml;
  const finished = (works || []).filter((item) => highestScore(item) >= 80 && !(item.failure_codes || []).length && item.selected_version_id);
  return `<section>
    <div class="section-title"><div><h2>发布中心</h2><p class="meta">从成品库选择作品，多选平台后生成发布任务。</p></div></div>
    <div class="publish-layout">
      <div class="table-panel">
        <table class="data-table">
          <thead><tr><th>成品</th><th>评分</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>${finished.map((work) => `<tr data-work-id="${escapeHtml(work.work_id || "")}">
            <td>${escapeHtml(work.title || work.theme || "未命名成品")}</td>
            <td>${highestScore(work)}</td>
            <td>准备发布</td>
            <td><button type="button" data-action="open-publish-modal">发布</button></td>
          </tr>`).join("") || `<tr><td colspan="4">暂无可发布成品</td></tr>`}</tbody>
        </table>
      </div>
      <div class="table-panel">
        <h3>发布任务</h3>
        <table class="data-table">
          <thead><tr><th>作品</th><th>平台</th><th>状态</th></tr></thead>
          <tbody>${(publishTasks || []).map((task) => `<tr><td>${escapeHtml(task.title)}</td><td>${escapeHtml(task.platforms.join("、"))}</td><td>${escapeHtml(task.status)}</td></tr>`).join("") || `<tr><td colspan="3">暂无发布任务</td></tr>`}</tbody>
        </table>
      </div>
    </div>
    <dialog id="publishModal" class="publish-modal">
      <form method="dialog">
        <h3>选择发布平台</h3>
        <div class="checkbox-grid platform-grid">
          ${platforms.map((platform) => `<label><input type="checkbox" name="platforms" value="${platform}">${platform}</label>`).join("")}
        </div>
        <p id="platformConfigHint" class="meta">平台未配置时会提示前往平台配置。</p>
        <div class="toolbar">
          <button type="button" data-action="confirm-publish">确认发布</button>
          <button type="button" class="secondary" data-action="close-publish-modal">取消</button>
        </div>
      </form>
    </dialog>
  </section>`;
}

export function renderPlatformConfig({ platformConfigs, helpers }) {
  const escapeHtml = helpers.escapeHtml;
  return `<section>
    <div class="section-title"><div><h2>平台配置</h2><p class="meta">维护不同发布平台的账号、Key/Cookie 占位字段、标题模板、标签、声明和格式。</p></div></div>
    <div class="table-panel">
      <table class="data-table">
        <thead><tr><th>平台名称</th><th>启用</th><th>账号标识</th><th>API Key / Cookie</th><th>标题模板</th><th>默认标签</th><th>发布声明</th><th>发布格式</th><th>最后验证</th><th>状态</th></tr></thead>
        <tbody>${platformConfigs.map((item) => `<tr>
          <td>${escapeHtml(item.platform)}</td>
          <td>${item.enabled ? "启用" : "停用"}</td>
          <td>${escapeHtml(item.account)}</td>
          <td>${escapeHtml(item.credential)}</td>
          <td>${escapeHtml(item.titleTemplate)}</td>
          <td>${escapeHtml(item.tags)}</td>
          <td>${escapeHtml(item.statement)}</td>
          <td>${escapeHtml(item.format)}</td>
          <td>${escapeHtml(item.lastVerifiedAt)}</td>
          <td>${escapeHtml(item.status)}</td>
        </tr>`).join("")}</tbody>
      </table>
    </div>
  </section>`;
}
