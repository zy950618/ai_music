import { CreationPanel } from "./CreationPanel.js";

export function WorkspacePanel(state) {
  return `
    <section id="loginScreen" class="login-screen ${state.currentUser ? "hidden" : ""}">
      <div class="login-panel">
        <h2>选择用户工作库</h2>
        <p class="meta">进入后仅显示该用户的作品、成品和发布任务。</p>
        <div class="login-users">
          ${state.users.map((user) => `<button type="button" class="login-user" data-login-user="${user.id}">
            <span class="avatar">${user.avatar}</span>
            <strong>${user.name}</strong>
            <span>${user.role}</span>
          </button>`).join("")}
        </div>
      </div>
    </section>
    <aside class="sidebar ${state.currentUser ? "" : "locked"}">
      <nav class="sidebar-nav" aria-label="后台导航">
        ${navButton("overview", "生产总览", true)}
        ${navButton("create", "新建创作")}
        ${navButton("works", "作品库")}
        ${navButton("finished", "成品库")}
        ${navButton("scores", "评分中心")}
        ${navButton("rework", "返工队列")}
        ${navButton("publish", "发布中心")}
        ${navButton("platforms", "平台配置")}
      </nav>
      <details class="maintenance-menu">
        <summary>系统维护</summary>
        <button type="button" data-tab="toolResearch">工具研究</button>
        <button type="button" data-tab="runEvidence">运行证据</button>
        <button type="button" data-tab="localGate">本地工具门禁</button>
        <button type="button" data-tab="auditLog">审计日志</button>
      </details>
    </aside>
    <section class="workspace-content ${state.currentUser ? "" : "locked"}">
      <div id="overview" class="tab"></div>
      <div id="create" class="tab hidden">${CreationPanel()}</div>
      <div id="works" class="tab hidden"></div>
      <div id="finished" class="tab hidden"></div>
      <div id="scores" class="tab hidden"></div>
      <div id="rework" class="tab hidden"></div>
      <div id="publish" class="tab hidden"></div>
      <div id="platforms" class="tab hidden"></div>
      <div id="toolResearch" class="tab hidden admin-tab"></div>
      <div id="runEvidence" class="tab hidden admin-tab"></div>
      <div id="localGate" class="tab hidden admin-tab"></div>
      <div id="auditLog" class="tab hidden admin-tab"></div>
    </section>`;
}

function navButton(tab, label, active = false) {
  return `<button type="button" data-tab="${tab}" class="${active ? "active" : ""}">${label}</button>`;
}
