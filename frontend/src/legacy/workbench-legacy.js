import { createWorkbenchController } from "../controllers/workbench-controller.js";

export function mountLegacyWorkbench() {
  createWorkbenchController().mount();
}
