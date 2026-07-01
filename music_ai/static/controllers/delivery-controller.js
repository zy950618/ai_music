import { renderPlatformConfig, renderPublishCenter } from "../components/DeliveryPanel.js";

export function createDeliveryController({ publishRoot, platformsRoot, getWorks, getState, helpers }) {
  let selectedWorkId = "";

  function render() {
    const state = getState();
    publishRoot.innerHTML = renderPublishCenter({
      works: getWorks(),
      publishTasks: state.publishTasks,
      platformConfigs: state.platformConfigs,
      helpers
    });
    platformsRoot.innerHTML = renderPlatformConfig({
      platformConfigs: state.platformConfigs,
      helpers
    });
    bind();
  }

  function bind() {
    publishRoot.querySelectorAll("[data-action]").forEach((node) => node.addEventListener("click", handleAction));
  }

  function handleAction(event) {
    const action = event.currentTarget.dataset.action;
    const row = event.currentTarget.closest("[data-work-id]");
    if (row) selectedWorkId = row.dataset.workId;
    const modal = publishRoot.querySelector("#publishModal");
    if (action === "open-publish-modal") {
      modal.showModal();
    }
    if (action === "close-publish-modal") {
      modal.close();
    }
    if (action === "confirm-publish") {
      confirmPublish(modal);
    }
  }

  function confirmPublish(modal) {
    const state = getState();
    const selectedPlatforms = Array.from(modal.querySelectorAll('input[name="platforms"]:checked')).map((node) => node.value);
    const work = getWorks().find((item) => item.work_id === selectedWorkId);
    if (!work || !selectedPlatforms.length) return;
    const missing = selectedPlatforms.filter((platform) => {
      const config = state.platformConfigs.find((item) => item.platform === platform);
      return !config || !config.enabled;
    });
    const hint = publishRoot.querySelector("#platformConfigHint");
    if (missing.length) {
      hint.textContent = `${missing.join("、")} 未配置，前往平台配置`;
      return;
    }
    state.publishTasks.push({
      id: `publish_${Date.now()}`,
      title: work.title || work.theme || work.work_id,
      platforms: selectedPlatforms,
      status: "已生成发布任务"
    });
    modal.close();
    render();
  }

  return { render };
}
