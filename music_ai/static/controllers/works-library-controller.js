import { renderFinishedLibrary, renderWorksLibrary } from "../components/WorksLibraryPanel.js";
import { renderWorkDetailDrawer } from "../components/WorkDetailDrawer.js";
import { workbenchApi } from "../services/workbench-api.js";

export function createWorksLibraryController({ root, finishedRoot = null, labels, helpers, onManualRework, api = workbenchApi, getCurrentUser = () => null }) {
  let worksState = { items: [], pagination: { page: 1, page_size: 10, total: 0, page_count: 0 }, filters: {}, sort: {} };
  let workFilters = { page: 1, page_size: 10, sort: "generatedAt:desc" };

  async function fetchWorks(updatePage = true) {
    const params = new URLSearchParams();
    const currentUser = getCurrentUser();
    if (currentUser?.workspace_id) params.set("workspace_id", currentUser.workspace_id);
    Object.entries(workFilters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== "") params.set(key, value);
    });
    const response = await api.works(params.toString());
    worksState = await response.json();
    if (updatePage) render();
  }

  function render() {
    root.innerHTML = renderWorksLibrary({ worksState, workFilters, labels, helpers });
    bind(root);
    if (finishedRoot) {
      finishedRoot.innerHTML = renderFinishedLibrary({ worksState, labels, helpers });
      bind(finishedRoot);
    }
  }

  function bind(scope) {
    const form = scope.querySelector("#workFilters");
    if (form) {
      form.addEventListener("input", () => {
        collectWorkFilters(form);
        fetchWorks();
      });
      form.addEventListener("change", () => {
        collectWorkFilters(form);
        fetchWorks();
      });
    }
    scope.querySelectorAll("[data-action]").forEach((node) => node.addEventListener("click", handleAction));
    scope.querySelectorAll('[data-role="work-select"]').forEach((node) => node.addEventListener("change", updateSelection));
  }

  async function handleAction(event) {
    const action = event.currentTarget.dataset.action;
    if (action === "prev-work-page") {
      workFilters.page = Math.max(1, Number((worksState.pagination || {}).page || 1) - 1);
      await fetchWorks();
      return;
    }
    if (action === "next-work-page") {
      workFilters.page = Number((worksState.pagination || {}).page || 1) + 1;
      await fetchWorks();
      return;
    }
    if (action === "bulk-archive") {
      await bulkArchive();
      return;
    }
    if (action === "bulk-delete") {
      await bulkDelete();
      return;
    }
    if (action === "close-work-detail") {
      closeDetail();
      return;
    }
    const row = event.currentTarget.closest("[data-work-id]");
    const item = row ? findItem(row.dataset.workId) : null;
    const versionRow = event.currentTarget.closest("[data-version-id]");
    const versionId = (versionRow && versionRow.dataset.versionId) || (row && row.dataset.versionId);
    if (!item) return;
    if (action === "show-work-detail") await showDetail(item.work_id);
    if (action === "manual-rework") await onManualRework(item.task_id, versionId || item.selected_version_id);
    if (action === "select-version" && versionId) await selectVersion(versionId);
    if (action === "move-finished") setNotice("已移入成品库。");
    if (action === "publish-work") setNotice("已送入发布中心。");
    if (action === "remove-finished") setNotice("已移出成品库。");
  }

  function collectWorkFilters(form) {
    const data = new FormData(form);
    workFilters = {
      q: data.get("q"),
      generated_from: data.get("generated_from"),
      generated_to: data.get("generated_to"),
      lifecycle: data.get("lifecycle"),
      sort: data.get("sort") || "generatedAt:desc",
      page_size: data.get("page_size") || 10,
      category: data.get("category"),
      mood: data.get("mood"),
      genre: data.get("genre"),
      min_score: data.get("min_score"),
      finished: data.get("finished"),
      page: 1
    };
  }

  async function showDetail(workId) {
    const response = await api.workDetail(workId);
    const detail = await response.json();
    const drawer = root.querySelector("#workDetailDrawer");
    drawer.classList.remove("hidden");
    drawer.dataset.workId = workId;
    drawer.innerHTML = renderWorkDetailDrawer(detail, labels, helpers);
    drawer.querySelectorAll("[data-action]").forEach((node) => node.addEventListener("click", handleAction));
  }

  function closeDetail() {
    const drawer = root.querySelector("#workDetailDrawer");
    if (drawer) drawer.classList.add("hidden");
  }

  async function selectVersion(versionId) {
    const response = await api.selectVersion(versionId);
    if (!response.ok) {
      setNotice(await response.text());
      return;
    }
    await fetchWorks();
  }

  async function bulkArchive() {
    const ids = selectedWorkIds();
    if (!ids.length) return;
    await api.bulkArchiveWorks(ids, "批量归档");
    await fetchWorks();
  }

  async function bulkDelete() {
    const ids = selectedWorkIds();
    if (!ids.length || !confirm(`确认软删除 ${ids.length} 个作品？`)) return;
    for (const id of ids) {
      await api.deleteWork(id, "批量软删除");
    }
    await fetchWorks();
  }

  function selectedWorkIds() {
    return Array.from(root.querySelectorAll('[data-role="work-select"]:checked')).map((node) => node.value).filter(Boolean);
  }

  function updateSelection() {
    const ids = selectedWorkIds();
    root.querySelectorAll(".work-card").forEach((card) => {
      card.classList.toggle("selected", ids.includes(card.dataset.workId));
    });
    const bar = root.querySelector("#bulkBar");
    const count = root.querySelector("#bulkCount");
    if (bar && count) {
      bar.classList.toggle("hidden", ids.length === 0);
      count.textContent = `已选择 ${ids.length} 个作品`;
    }
  }

  function setNotice(message) {
    const notice = root.querySelector("#workNotice") || document.getElementById("globalNotice");
    if (notice) notice.textContent = message;
  }

  function findItem(workId) {
    return (worksState.items || []).find((item) => item.work_id === workId);
  }

  return { fetchWorks, render, getWorksState: () => worksState };
}
