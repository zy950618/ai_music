export const workbenchApi = {
  create(payload) {
    return fetch("/api/create", jsonPost(payload));
  },
  createAsync(payload) {
    return fetch("/api/create-async", jsonPost(payload));
  },
  job(jobId) {
    return fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
  },
  tasks() {
    return fetch("/api/tasks");
  },
  works(query = "") {
    return fetch(`/api/works${query ? `?${query}` : ""}`);
  },
  workDetail(workId) {
    return fetch(`/api/works/${encodeURIComponent(workId)}`);
  },
  manualRework(taskId, payload) {
    return fetch(`/api/tasks/${encodeURIComponent(taskId)}/manual-rework`, jsonPost(payload));
  },
  selectVersion(versionId) {
    return fetch(`/api/versions/${encodeURIComponent(versionId)}/select`, { method: "POST" });
  },
  deleteWork(workId, reason = "用户软删除") {
    return fetch(`/api/works/${encodeURIComponent(workId)}/delete`, jsonPost({ reason }));
  },
  bulkArchiveWorks(workIds, reason = "批量归档") {
    return fetch("/api/works/bulk-archive", jsonPost({ work_ids: workIds, reason }));
  }
};

function jsonPost(payload) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  };
}
