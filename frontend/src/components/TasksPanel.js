export function renderTasksPanel({ tasks = [], helpers }) {
  return `<div class="table-panel">
    <table class="data-table">
      <thead><tr><th>任务</th><th>作品</th><th>候选数</th><th>状态</th></tr></thead>
      <tbody>${tasks.map((task) => `<tr>
        <td>${helpers.escapeHtml(task.task_id || "-")}</td>
        <td>${helpers.escapeHtml((task.request_data && (task.request_data.title || task.request_data.theme)) || task.work_id || "-")}</td>
        <td>${(task.versions || []).length}</td>
        <td>${helpers.escapeHtml(task.rights_status || "-")}</td>
      </tr>`).join("")}</tbody>
    </table>
  </div>`;
}
