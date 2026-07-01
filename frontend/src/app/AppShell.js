import { AppHeader } from "../components/AppHeader.js";
import { WorkspacePanel } from "../components/WorkspacePanel.js";
import { createWorkbenchState } from "../state/workbench-state.js";

export function mountAppShell(root) {
  if (!root) {
    throw new Error("缺少工作台挂载节点");
  }
  const state = createWorkbenchState();
  root.innerHTML = `
    ${AppHeader()}
    <main class="admin-shell">
      ${WorkspacePanel(state)}
    </main>
  `;
  document.documentElement.dataset.themeMode = state.theme.mode;
  document.documentElement.dataset.themeColor = state.theme.color;
  return state;
}
