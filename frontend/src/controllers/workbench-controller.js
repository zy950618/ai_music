import { renderScoresPanel, renderReworkPanel } from "../components/ScoresPanel.js";
import { createCreationController } from "./creation-controller.js";
import { createDeliveryController } from "./delivery-controller.js";
import { createTabsController } from "./tabs-controller.js";
import { createWorksLibraryController } from "./works-library-controller.js";
import { workbenchApi } from "../services/workbench-api.js";
import {
  agentLabels,
  failureLabels,
  genreLabels,
  loopDecisionLabels,
  rightsLabels,
  scoreLabels,
  sortFieldLabels,
  statusLabels
} from "../ui/labels.js";
import { escapeHtml, fileUrl, formatDuration, labelOf } from "../ui/helpers.js";

const moduleTitles = {
  overview: "生产总览",
  create: "新建创作",
  works: "作品库",
  finished: "成品库",
  scores: "评分中心",
  rework: "返工队列",
  publish: "发布中心",
  platforms: "平台配置",
  toolResearch: "系统维护",
  runEvidence: "系统维护",
  localGate: "系统维护",
  auditLog: "系统维护"
};

export function createWorkbenchController({ root = document, state = window.workbenchShellState, api = workbenchApi } = {}) {
  const $ = (id) => root.getElementById(id);
  let tasks = [];

  const helpers = { escapeHtml, fileUrl, formatDuration, labelOf };
  const labels = {
    agentLabels,
    failureLabels,
    genreLabels,
    loopDecisionLabels,
    rightsLabels,
    scoreLabels,
    sortFieldLabels,
    statusLabels
  };

  const tabsController = createTabsController({
    root,
    onSelect: (tab) => {
      state.currentModule = moduleTitles[tab] || "生产总览";
      $("moduleTitle").textContent = state.currentModule;
    }
  });

  const worksLibrary = createWorksLibraryController({
    root: $("works"),
    finishedRoot: $("finished"),
    labels,
    helpers,
    onManualRework: manualRework,
    api,
    getCurrentUser: () => state.currentUser
  });

  const creationController = createCreationController({
    load,
    root,
    api,
    getCurrentUser: () => state.currentUser
  });

  const deliveryController = createDeliveryController({
    publishRoot: $("publish"),
    platformsRoot: $("platforms"),
    getWorks: () => worksLibrary.getWorksState().items || [],
    getState: () => state,
    helpers
  });

  function mount() {
    bindLogin();
    bindTheme();
    tabsController.mount();
    creationController.mount();
    applyUserState();
    if (state.currentUser) load();
  }

  async function load() {
    if (!state.currentUser) return;
    const [tasksResponse] = await Promise.all([api.tasks()]);
    tasks = await tasksResponse.json();
    await worksLibrary.fetchWorks(false);
    renderOverview();
    worksLibrary.render();
    $("scores").innerHTML = renderScoresPanel({ works: worksLibrary.getWorksState().items || [], labels, helpers });
    $("rework").innerHTML = renderReworkPanel({ works: worksLibrary.getWorksState().items || [], labels, helpers });
    renderMaintenance();
    deliveryController.render();
  }

  async function manualRework(taskId, versionId) {
    if (!taskId) return;
    await api.manualRework(taskId, {
      version_id: versionId,
      failure_code: "WEAK_HOOK",
      notes: "从产品后台打回返工"
    });
    await load();
  }

  function renderOverview() {
    const works = worksLibrary.getWorksState().items || [];
    const finished = works.filter((item) => Number(item.score_total || 0) >= 80 && !(item.failure_codes || []).length);
    const reworkCount = works.filter((item) => Number(item.score_total || 0) < 80 || (item.failure_codes || []).length).length;
    $("overview").innerHTML = `<section>
      <div class="section-title"><div><h2>生产总览</h2><p class="meta">当前用户工作库的创作、成品、发布和返工概况。</p></div></div>
      <div class="metric-grid">
        ${metric("作品", works.length)}
        ${metric("成品", finished.length)}
        ${metric("待返工", reworkCount)}
        ${metric("发布任务", state.publishTasks.length)}
      </div>
      <p id="globalNotice" class="meta"></p>
    </section>`;
  }

  function renderMaintenance() {
    $("toolResearch").innerHTML = maintenancePage("工具研究", "仅管理员用于沉淀外部工具研究结论，不进入普通创作路径。");
    $("runEvidence").innerHTML = maintenancePage("运行证据", "记录测试、自测和运行日志，普通用户默认不进入。");
    $("localGate").innerHTML = maintenancePage("本地工具门禁", "维护本地工具调用白名单、配额和审计记录。");
    $("auditLog").innerHTML = maintenancePage("审计日志", "记录归档、删除、发布和返工处理动作。");
  }

  function maintenancePage(title, body) {
    return `<section><div class="section-title"><div><h2>${title}</h2><p class="meta">${body}</p></div></div><article class="empty-state"><h3>管理员维护区</h3><p class="meta">该页面默认折叠，不属于普通用户主流程。</p></article></section>`;
  }

  function bindLogin() {
    root.querySelectorAll("[data-login-user]").forEach((button) => {
      button.addEventListener("click", async () => {
        state.currentUser = state.users.find((user) => user.id === button.dataset.loginUser);
        localStorage.setItem("aiMusicWorkbench.userId", state.currentUser.id);
        applyUserState();
        await load();
      });
    });
    root.querySelector('[data-action="logout"]')?.addEventListener("click", () => {
      state.currentUser = null;
      localStorage.removeItem("aiMusicWorkbench.userId");
      applyUserState();
    });
  }

  function bindTheme() {
    root.querySelector('[data-action="theme-mode"]')?.addEventListener("click", () => {
      state.theme.mode = state.theme.mode === "dark" ? "light" : "dark";
      persistTheme();
    });
    root.querySelectorAll("[data-theme-color]").forEach((button) => {
      button.addEventListener("click", () => {
        state.theme.color = button.dataset.themeColor;
        persistTheme();
      });
    });
  }

  function persistTheme() {
    localStorage.setItem("aiMusicWorkbench.theme", JSON.stringify(state.theme));
    document.documentElement.dataset.themeMode = state.theme.mode;
    document.documentElement.dataset.themeColor = state.theme.color;
  }

  function applyUserState() {
    const loggedIn = Boolean(state.currentUser);
    $("loginScreen").classList.toggle("hidden", loggedIn);
    root.querySelector(".sidebar")?.classList.toggle("locked", !loggedIn);
    root.querySelector(".workspace-content")?.classList.toggle("locked", !loggedIn);
    $("userBadge").classList.toggle("hidden", !loggedIn);
    if (loggedIn) {
      $("userAvatar").textContent = state.currentUser.avatar;
      $("userName").textContent = state.currentUser.name;
    }
  }

  function metric(label, value) {
    return `<article class="metric"><span>${label}</span><strong>${value}</strong></article>`;
  }

  return { mount, load };
}
