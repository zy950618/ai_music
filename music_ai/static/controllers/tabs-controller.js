export function createTabsController({ root = document, onSelect = () => {} } = {}) {
  function mount() {
    root.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => selectTab(button.dataset.tab));
    });
  }

  function selectTab(tabId) {
    root.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("hidden", tab.id !== tabId));
    root.querySelectorAll("[data-tab]").forEach((button) => button.classList.toggle("active", button.dataset.tab === tabId));
    onSelect(tabId);
  }

  return { mount, selectTab };
}
