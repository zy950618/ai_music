import { mountAppShell } from "./app/AppShell.js";
import { workbenchApi } from "./services/workbench-api.js";
import { mountLegacyWorkbench } from "./legacy/workbench-legacy.js";

const shellState = mountAppShell(document.getElementById("app"));
window.workbenchApi = workbenchApi;
window.workbenchShellState = shellState;
mountLegacyWorkbench();
