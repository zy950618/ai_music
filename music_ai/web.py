from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .automation import DailyAutomationScheduler, DailyAutomationService
from .engine import CreationEngine
from .models import MusicCreationRequest, RightsConfiguration
from .repository import ResultRepository, result_from_dict
from .skills import get_rework_rule, skills_snapshot


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 音乐制作工作台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f7f4;
      --ink: #1d1f23;
      --muted: #69707a;
      --line: #d9d9d2;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-ink: #ffffff;
      --warn: #9f580a;
      --bad: #b42318;
      --good: #157347;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 22px;
      border-bottom: 1px solid var(--line);
      background: #fbfbf8;
    }
    h1 { margin: 0; font-size: 20px; font-weight: 650; }
    main { display: grid; grid-template-columns: 320px 1fr; min-height: calc(100vh - 62px); }
    aside {
      border-right: 1px solid var(--line);
      padding: 18px;
      background: #fbfbf8;
    }
    section { padding: 20px; }
    label { display: block; margin: 10px 0 5px; color: var(--muted); font-size: 12px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 76px; resize: vertical; }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: var(--accent-ink);
      border-radius: 6px;
      padding: 9px 12px;
      font: inherit;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: var(--accent); }
    button:disabled { opacity: .55; cursor: default; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
    .tabs button { background: #fff; color: var(--ink); border-color: var(--line); }
    .tabs button.active { background: var(--ink); color: #fff; border-color: var(--ink); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--panel);
    }
    .item h3 { margin: 0 0 8px; font-size: 15px; }
    .meta { color: var(--muted); font-size: 12px; line-height: 1.6; }
    .status { display: inline-block; padding: 3px 7px; border-radius: 999px; font-size: 12px; background: #eef2f1; }
    .status.good { color: var(--good); }
    .status.warn { color: var(--warn); }
    .status.bad { color: var(--bad); }
    audio { width: 100%; margin-top: 10px; }
    .downloads { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .downloads a {
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 5px 8px;
      background: #fff;
      font-size: 12px;
    }
    .row { display: flex; gap: 8px; align-items: center; }
    .row > * { flex: 1; }
    .toolbar { display: flex; gap: 8px; margin-top: 12px; }
    .hidden { display: none; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; background: #f1f1ed; padding: 10px; border-radius: 6px; }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI 音乐制作工作台</h1>
    <span id="summary" class="meta"></span>
  </header>
  <main>
    <aside>
      <form id="createForm">
        <label>标题</label>
        <input name="title" value="夜色里的新歌">
        <label>主题</label>
        <textarea name="theme">城市夜晚里的希望和重新开始</textarea>
        <div class="row">
          <div>
            <label>类型</label>
            <select name="mode">
              <option value="song">歌曲</option>
              <option value="instrumental">纯音乐</option>
              <option value="bgm">BGM</option>
              <option value="loop">循环</option>
              <option value="short_video">短视频</option>
              <option value="game">游戏</option>
              <option value="film">影视</option>
            </select>
          </div>
          <div>
            <label>时长</label>
            <input name="duration_sec" type="number" min="8" max="120" value="18">
          </div>
        </div>
        <label>风格</label>
        <input name="genre" value="pop,electronic">
        <label>情绪</label>
        <input name="mood" value="warm,hopeful,catchy">
        <label>受众</label>
        <input name="audience" value="短视频创作者和独立音乐听众">
        <label>用途</label>
        <input name="use_case" value="AI 音乐创作引擎验证">
        <div class="row">
          <div>
            <label>BPM</label>
            <input name="bpm" type="number" value="104">
          </div>
          <div>
            <label>Key</label>
            <input name="key" value="C">
          </div>
        </div>
        <label>人声</label>
        <select name="vocal_required">
          <option value="true">需要</option>
          <option value="false">不需要</option>
        </select>
        <label>外部下载 URL</label>
        <input name="download_url" placeholder="可留空">
        <div class="toolbar">
          <button type="submit">创建</button>
          <button type="button" class="secondary" id="refreshBtn">刷新</button>
        </div>
        <div class="toolbar">
          <button type="button" class="secondary" id="dailyBtn">自动生成10条</button>
          <button type="button" class="secondary" id="reworkBtn">处理返工</button>
        </div>
      </form>
    </aside>
    <section>
      <div id="opsPanel" class="item" style="margin-bottom: 12px;"></div>
      <nav class="tabs">
        <button data-tab="tasks" class="active">每日任务</button>
        <button data-tab="works">作品库</button>
        <button data-tab="scores">评分中心</button>
        <button data-tab="delivery">交付与授权</button>
      </nav>
      <div id="tasks" class="tab"></div>
      <div id="works" class="tab hidden"></div>
      <div id="scores" class="tab hidden"></div>
      <div id="delivery" class="tab hidden"></div>
    </section>
  </main>
    <script>
      let state = [];
      let reworkHistory = {events: [], summary: {}};
      let opsState = {};
    const $ = (id) => document.getElementById(id);
    const fileUrl = (path) => path ? `/files?path=${encodeURIComponent(path)}` : "";
    const splitList = (value) => value.split(",").map((x) => x.trim()).filter(Boolean);

    document.querySelectorAll(".tabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab").forEach((tab) => tab.classList.add("hidden"));
        btn.classList.add("active");
        $(btn.dataset.tab).classList.remove("hidden");
      });
    });

    $("refreshBtn").addEventListener("click", load);
    $("dailyBtn").addEventListener("click", async () => {
      const response = await fetch("/api/automation/daily", {method: "POST"});
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    });
    $("reworkBtn").addEventListener("click", async () => {
      const response = await fetch("/api/automation/rework", {method: "POST"});
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    });
    $("createForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      const payload = {
        title: form.get("title"),
        mode: form.get("mode"),
        language: "zh",
        theme: form.get("theme"),
        mood: splitList(form.get("mood")),
        genre: splitList(form.get("genre")),
        audience: form.get("audience"),
        use_case: form.get("use_case"),
        duration_sec: Number(form.get("duration_sec")),
        bpm: Number(form.get("bpm")),
        key: form.get("key"),
        vocal_required: form.get("vocal_required") === "true",
        forbidden: ["真实歌手模仿", "复制已有歌曲旋律"],
        export_formats: ["wav"]
      };
      const downloadUrl = String(form.get("download_url") || "").trim();
      const response = await fetch(downloadUrl ? "/api/import-url" : "/api/create", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(downloadUrl ? {request: payload, url: downloadUrl, duration_sec: payload.duration_sec} : payload)
      });
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    });

    async function configureRights(taskId) {
      const response = await fetch(`/api/tasks/${taskId}/configure-rights`, {method: "POST"});
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    }

    async function createDeliveryPackage(taskId) {
      const response = await fetch(`/api/tasks/${taskId}/delivery-package`, {method: "POST"});
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    }

    async function manualRework(taskId, versionId) {
      const response = await fetch(`/api/tasks/${taskId}/manual-rework`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({version_id: versionId, failure_code: "WEAK_HOOK", notes: "manual UI re-optimization"})
      });
      if (!response.ok) {
        alert(await response.text());
      }
      await load();
    }

    async function load() {
      const [tasksResponse, historyResponse, opsResponse] = await Promise.all([
        fetch("/api/tasks"),
        fetch("/api/rework-history"),
        fetch("/api/ops")
      ]);
      state = await tasksResponse.json();
      reworkHistory = await historyResponse.json();
      opsState = await opsResponse.json();
      const versionCount = state.reduce((sum, task) => sum + (task.versions ? task.versions.length : 0), 0);
      const passRate = (opsState.quality && Number(opsState.quality.qa_pass_rate) !== undefined)
        ? `${opsState.quality.qa_pass_rate}%`
        : "N/A";
      $("summary").textContent = `任务 ${state.length} / 版本 ${versionCount} / QA通过率 ${passRate}`;
      renderOpsCenter();
      renderTasks();
      renderWorks();
      renderScores();
      renderDelivery();
    }

    function renderOpsCenter() {
      const quality = opsState.quality || {};
      const rights = opsState.rights_status || {};
      const rework = opsState.rework || {};
      const scheduler = opsState.scheduler_state || {};
      const nextAgentRows = Object.entries(quality.next_agent_counts || {}).slice(0, 5).map(([agent, count]) => `${agent}: ${count}`).join(" | ") || "-";
      const failRows = Object.entries(quality.failure_counts || {}).slice(0, 5).map(([code, count]) => `${code}: ${count}`).join(" | ") || "-";
      $("opsPanel").innerHTML = `
        <p class="meta"><span style="display: inline-block; padding: 3px 7px; border-radius: 999px; background: #f0efea; color: #1d1f23; font-size: 12px;">${opsState.generated_at || "-"}</span></p>
        <div class="grid">
          <article class="item">
            <h3>任务健康</h3>
            <p class="meta">任务数：${opsState.task_count || 0}</p>
            <p class="meta">版本数：${opsState.version_count || 0}</p>
            <p class="meta">版本通过：${quality.version_pass || 0}，失败：${quality.version_fail || 0}</p>
            <p class="meta">QA通过率：${quality.qa_pass_rate != null ? quality.qa_pass_rate : 0}%</p>
            <p class="meta">平均得分：${quality.average_score || 0}</p>
          </article>
          <article class="item">
            <h3>发布与重做</h3>
            <p class="meta">权限：missing ${rights.missing || 0} / configured ${rights.configured || 0} / review ${rights.review_required || 0}</p>
            <p class="meta">重做队列：${rework.queued || 0}</p>
            <p class="meta">重做阻断：${(rework.rework_budget_summary && rework.rework_budget_summary.blocked) || 0}</p>
            <p class="meta">下次执行窗口：${scheduler.last_scheduler_run_id || "无"}</p>
          </article>
          <article class="item">
            <h3>循环策略 Top</h3>
            <p class="meta">失败Top：${failRows}</p>
            <p class="meta">下一归属Top：${nextAgentRows}</p>
          </article>
        </div>
      `;
    }

    function renderTasks() {
      const events = reworkHistory.events || [];
      const summary = reworkHistory.summary || {};
      const reworkPanel = events.length ? `
        <h2>返工历史</h2>
        <div class="grid">${events.slice(0, 12).map((event) => `
          <article class="item">
            <h3>${event.failure_code || "unknown"}</h3>
            <span class="status ${event.created_score_total >= 80 ? "good" : "warn"}">深度 ${event.rework_depth || 0}</span>
            <p class="meta">${event.source_work_id || event.source_task_id || "-"} → ${event.created_work_id || event.created_task_id || "-"}</p>
            <p class="meta">Agent ${event.target_agent || "-"} | Skill ${event.skill_id || "-"}</p>
            <p class="meta">根任务 ${event.root_task_id || "-"} | ${event.created_at || "-"}</p>
            <p class="meta">新评分 ${event.created_score_total ?? "-"} | 授权 ${event.created_rights_status || "-"}</p>
          </article>`).join("")}</div>` : `<p class="meta">暂无返工历史</p>`;
      $("tasks").innerHTML = `
        <div class="grid">${state.map((task) => `
        <article class="item">
          <h3>${task.work_id}</h3>
          <span class="status ${task.rights_status === "configured" ? "good" : "warn"}">${task.rights_status}</span>
          <p class="meta">${task.brief}</p>
          <p class="meta">候选 ${task.versions.length} | 选中 ${task.selected_version_id || "-"}</p>
        </article>`).join("")}</div>`;
    }

    function renderWorks() {
      const versions = state.flatMap((task) => task.versions.map((version) => ({task, version})));
      $("works").innerHTML = `<div class="grid">${versions.map(({task, version}) => {
        const preview = version.export_files.find((f) => f.kind === "preview" && f.path);
        const files = version.export_files.filter((f) => f.ready && (f.path || f.download_url));
        return `<article class="item">
          <h3>${version.title}</h3>
          <p class="meta">${version.version_id} | ${version.status} | ${version.bpm || "-"} BPM | ${version.key || "-"}</p>
          <p class="meta">${((version.generation_route || {}).selection || {}).selected_provider_id || (version.generation_route || {}).provider || version.model_provider} | ${version.model_name || "-"}</p>
          ${preview ? `<audio controls src="${fileUrl(preview.path)}"></audio>` : ""}
          <div class="downloads">${files.map((f) => `<a href="${f.download_url || fileUrl(f.path)}" download>${f.kind}</a>`).join("")}</div>
          <div class="toolbar">
            <button onclick="manualRework('${task.task_id}', '${version.version_id}')">Manual Rework</button>
          </div>
          <p class="meta">任务 ${task.task_id}</p>
        </article>`;
      }).join("")}</div>`;
    }

    function renderScores() {
      const versions = state.flatMap((task) => task.versions.map((version) => ({task, version})));
      $("scores").innerHTML = `<div class="grid">${versions.map(({version}) => `
        <article class="item">
          <h3>${version.version_id}</h3>
          <span class="status ${(version.score_total || 0) >= 80 ? "good" : "bad"}">${version.score_total || 0}</span>
          <p class="meta">状态 ${version.status}</p>
          <pre>${JSON.stringify((version.generation_route || {}).selection || {}, null, 2) || "No generation route"}</pre>
          <pre>${Object.entries(version.score_breakdown || {}).map(([key, value]) => `${key}: ${value}`).join("\\n") || "No score breakdown"}</pre>
          <pre>${((version.audio_analysis || {}).technical_flags || []).join("\\n") || "No technical flags"}</pre>
          <pre>${(version.failure_codes || []).length ? version.failure_codes.join("\\n") : "No failure codes"}</pre>
        </article>`).join("")}</div>`;
    }

    function renderDelivery() {
      $("delivery").innerHTML = `<div class="grid">${state.map((task) => {
        const selected = task.versions.find((v) => v.version_id === task.selected_version_id) || task.versions[0];
        const master = selected ? selected.export_files.find((f) => f.kind === "master") : null;
        const licenses = selected ? selected.export_files.filter((f) => f.kind === "license_pack") : [];
        const packages = selected ? selected.export_files.filter((f) => f.kind === "delivery_package") : [];
        return `<article class="item">
          <h3>${task.work_id}</h3>
          <span class="status ${task.rights_status === "configured" ? "good" : "warn"}">${task.rights_status}</span>
          <p class="meta">master ${master && master.ready ? "ready" : "blocked"} ${master && master.blocked_reason ? "| " + master.blocked_reason : ""}</p>
          <div class="downloads">${licenses.concat(packages).map((f) => `<a href="${fileUrl(f.path)}" download>${f.kind}</a>`).join("")}</div>
          <div class="toolbar">
            <button onclick="configureRights('${task.task_id}')" ${task.rights_status === "configured" ? "disabled" : ""}>配置授权</button>
            <button onclick="createDeliveryPackage('${task.task_id}')" ${task.rights_status === "configured" ? "" : "disabled"}>交付包</button>
          </div>
        </article>`;
      }).join("")}</div>`;
    }

    function formatLoopState(version) {
      if (!version || !version.loop_state) {
        return "LOOP state unavailable";
      }
      return `${version.loop_state.decision} / ${version.loop_state.next_agent} / ${version.loop_state.next_action}`;
    }

    function renderDelivery() {
      const deliveryCards = state.map((task) => {
        const selected = task.versions.find((v) => v.version_id === task.selected_version_id) || task.versions[0];
        const master = selected ? selected.export_files.find((f) => f.kind === "master") : null;
        const deliverables = selected ? selected.export_files.filter((f) => f.kind === "license_pack" || f.kind === "delivery_package") : [];
        return `<article class="item">
          <h3>${task.work_id}</h3>
          <span class="status ${task.rights_status === "configured" ? "good" : "warn"}">${task.rights_status}</span>
          <p class="meta">任务 ${task.task_id}</p>
          <p class="meta">版本 ${selected ? selected.version_id : "-"}</p>
          ${selected ? `<p class="meta">状态 ${selected.status}</p>` : ""}
          ${selected ? `<p class="meta">${formatLoopState(selected)}</p>` : ""}
          <p class="meta">master ${master && master.ready ? "ready" : "blocked"} ${master && master.blocked_reason ? "| " + master.blocked_reason : ""}</p>
          <div class="downloads">${deliverables.map((f) => `<a href="${fileUrl(f.path)}" download>${f.kind}</a>`).join("")}</div>
          <div class="toolbar">
            <button onclick="configureRights('${task.task_id}')" ${task.rights_status === "configured" ? "disabled" : ""}>Configure Rights</button>
            <button onclick="createDeliveryPackage('${task.task_id}')" ${task.rights_status !== "configured" ? "disabled" : ""}>Create Delivery Package</button>
          </div>
        </article>`;
      }).join("");
      $("delivery").innerHTML = `<div class="grid">${deliveryCards}</div>`;
    }

    load();
  </script>
</body>
</html>
"""


def render_index_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 音乐制作工作台</title>
  <style>
    :root {
      --bg: #f6f5f1;
      --surface: #ffffff;
      --ink: #1e2329;
      --muted: #66717f;
      --line: #d8d6ce;
      --accent: #0f766e;
      --accent-weak: #e6f2f0;
      --warn: #9a5b00;
      --bad: #b42318;
      --good: #137447;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 22px;
      border-bottom: 1px solid var(--line);
      background: #fbfaf7;
    }
    h1 { margin: 0; font-size: 20px; font-weight: 650; }
    main { display: grid; grid-template-columns: 320px 1fr; min-height: calc(100vh - 62px); }
    aside {
      border-right: 1px solid var(--line);
      padding: 18px;
      background: #fbfaf7;
    }
    section { padding: 20px; }
    label { display: block; margin: 10px 0 5px; color: var(--muted); font-size: 12px; }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
    }
    textarea { min-height: 76px; resize: vertical; }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 9px 12px;
      font: inherit;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: var(--accent); }
    button:disabled { opacity: .55; cursor: default; }
    .tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 18px; }
    .tabs button { background: #fff; color: var(--ink); border-color: var(--line); }
    .tabs button.active { background: var(--ink); color: #fff; border-color: var(--ink); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--surface);
    }
    .item h3 { margin: 0 0 8px; font-size: 15px; }
    .meta { color: var(--muted); font-size: 12px; line-height: 1.6; }
    .status { display: inline-block; padding: 3px 7px; border-radius: 999px; font-size: 12px; background: var(--accent-weak); }
    .status.good { color: var(--good); }
    .status.warn { color: var(--warn); }
    .status.bad { color: var(--bad); }
    audio { width: 100%; margin-top: 10px; }
    .downloads { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .downloads a {
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 5px 8px;
      background: #fff;
      font-size: 12px;
    }
    .row { display: flex; gap: 8px; align-items: center; }
    .row > * { flex: 1; }
    .toolbar { display: flex; gap: 8px; margin-top: 12px; }
    .hidden { display: none; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; background: #f0efea; padding: 10px; border-radius: 6px; }
    @media (max-width: 820px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <header>
    <h1>AI 音乐制作工作台</h1>
    <span id="summary" class="meta"></span>
  </header>
  <main>
    <aside>
      <form id="createForm">
        <label>标题</label>
        <input name="title" value="夜色里的新歌">
        <label>主题</label>
        <textarea name="theme">城市夜晚里的希望和重新开始</textarea>
        <div class="row">
          <div>
            <label>类型</label>
            <select name="mode">
              <option value="song">歌曲</option>
              <option value="instrumental">纯音乐</option>
              <option value="bgm">BGM</option>
              <option value="loop">循环</option>
              <option value="short_video">短视频</option>
              <option value="game">游戏</option>
              <option value="film">影视</option>
              <option value="children">儿童</option>
              <option value="classical">古典</option>
            </select>
          </div>
          <div>
            <label>时长</label>
            <input name="duration_sec" type="number" min="8" max="120" value="18">
          </div>
        </div>
        <label>风格</label>
        <input name="genre" value="pop,electronic">
        <label>情绪</label>
        <input name="mood" value="warm,hopeful,catchy">
        <label>受众</label>
        <input name="audience" value="短视频创作者和独立音乐听众">
        <label>用途</label>
        <input name="use_case" value="AI 音乐创作引擎验证">
        <div class="row">
          <div>
            <label>BPM</label>
            <input name="bpm" type="number" value="104">
          </div>
          <div>
            <label>Key</label>
            <input name="key" value="C">
          </div>
        </div>
        <label>人声</label>
        <select name="vocal_required">
          <option value="true">需要</option>
          <option value="false">不需要</option>
        </select>
        <label>外部生成下载 URL</label>
        <input name="download_url" placeholder="可留空">
        <div class="toolbar">
          <button type="submit">创建</button>
          <button type="button" class="secondary" id="refreshBtn">刷新</button>
        </div>
        <div class="toolbar">
          <button type="button" class="secondary" id="dailyBtn">自动生成10条</button>
          <button type="button" class="secondary" id="reworkBtn">处理返工</button>
        </div>
      </form>
    </aside>
    <section>
      <nav class="tabs">
        <button data-tab="tasks" class="active">每日任务</button>
        <button data-tab="works">作品库</button>
        <button data-tab="scores">评分中心</button>
        <button data-tab="delivery">交付与授权</button>
      </nav>
      <div id="tasks" class="tab"></div>
      <div id="works" class="tab hidden"></div>
      <div id="scores" class="tab hidden"></div>
      <div id="delivery" class="tab hidden"></div>
    </section>
  </main>
  <script>
    let state = [];
    let reworkHistory = {events: [], summary: {}};
    let opsState = {};
    const $ = (id) => document.getElementById(id);
    const fileUrl = (path) => path ? `/files?path=${encodeURIComponent(path)}` : "";
    const splitList = (value) => value.split(",").map((x) => x.trim()).filter(Boolean);

    document.querySelectorAll(".tabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab").forEach((tab) => tab.classList.add("hidden"));
        btn.classList.add("active");
        $(btn.dataset.tab).classList.remove("hidden");
      });
    });

    $("refreshBtn").addEventListener("click", load);
    $("dailyBtn").addEventListener("click", async () => {
      const button = $("dailyBtn");
      button.disabled = true;
      button.textContent = "生成中";
      try {
        const response = await fetch("/api/automation/daily", {method: "POST"});
        if (!response.ok) alert(await response.text());
        await load();
      } finally {
        button.disabled = false;
        button.textContent = "自动生成10条";
      }
    });
    $("reworkBtn").addEventListener("click", async () => {
      const response = await fetch("/api/automation/rework", {method: "POST"});
      if (!response.ok) alert(await response.text());
      await load();
    });
    $("createForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      const payload = {
        title: form.get("title"),
        mode: form.get("mode"),
        language: "zh",
        theme: form.get("theme"),
        mood: splitList(form.get("mood")),
        genre: splitList(form.get("genre")),
        audience: form.get("audience"),
        use_case: form.get("use_case"),
        duration_sec: Number(form.get("duration_sec")),
        bpm: Number(form.get("bpm")),
        key: form.get("key"),
        vocal_required: form.get("vocal_required") === "true",
        forbidden: ["真实歌手模仿", "复制已有歌曲旋律"],
        export_formats: ["wav"]
      };
      const downloadUrl = String(form.get("download_url") || "").trim();
      const response = await fetch(downloadUrl ? "/api/import-url" : "/api/create", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(downloadUrl ? {request: payload, url: downloadUrl, duration_sec: payload.duration_sec} : payload)
      });
      if (!response.ok) alert(await response.text());
      await load();
    });

    async function configureRights(taskId) {
      const response = await fetch(`/api/tasks/${taskId}/configure-rights`, {method: "POST"});
      if (!response.ok) alert(await response.text());
      await load();
    }

    async function createDeliveryPackage(taskId) {
      const response = await fetch(`/api/tasks/${taskId}/delivery-package`, {method: "POST"});
      if (!response.ok) alert(await response.text());
      await load();
    }

    async function load() {
      const [tasksResponse, historyResponse, opsResponse] = await Promise.all([
        fetch("/api/tasks"),
        fetch("/api/rework-history"),
        fetch("/api/ops")
      ]);
      state = await tasksResponse.json();
      reworkHistory = await historyResponse.json();
      opsState = await opsResponse.json();
      const versionCount = state.reduce((sum, task) => sum + (task.versions ? task.versions.length : 0), 0);
      const passRate = (opsState.quality && Number(opsState.quality.qa_pass_rate) !== undefined)
        ? `${opsState.quality.qa_pass_rate}%`
        : "N/A";
      $("summary").textContent = `任务 ${state.length} / 版本 ${versionCount} / QA通过率 ${passRate}`;
      renderOpsCenter();
      renderTasks();
      renderWorks();
      renderScores();
      renderDelivery();
    }

    function renderOpsCenter() {
      const quality = opsState.quality || {};
      const rights = opsState.rights_status || {};
      const rework = opsState.rework || {};
      const scheduler = opsState.scheduler_state || {};
      const nextAgentRows = Object.entries(quality.next_agent_counts || {}).slice(0, 5).map(([agent, count]) => `${agent}: ${count}`).join(" | ") || "-";
      const failRows = Object.entries(quality.failure_counts || {}).slice(0, 5).map(([code, count]) => `${code}: ${count}`).join(" | ") || "-";
      $("opsPanel").innerHTML = `
        <p class="meta"><span style="display: inline-block; padding: 3px 7px; border-radius: 999px; background: #f0efea; color: #1d1f23; font-size: 12px;">${opsState.generated_at || "-"}</span></p>
        <div class="grid">
          <article class="item">
            <h3>任务健康</h3>
            <p class="meta">任务数：${opsState.task_count || 0}</p>
            <p class="meta">版本数：${opsState.version_count || 0}</p>
            <p class="meta">版本通过：${quality.version_pass || 0}，失败：${quality.version_fail || 0}</p>
            <p class="meta">QA通过率：${quality.qa_pass_rate != null ? quality.qa_pass_rate : 0}%</p>
            <p class="meta">平均得分：${quality.average_score || 0}</p>
          </article>
          <article class="item">
            <h3>发布与重做</h3>
            <p class="meta">权限：missing ${rights.missing || 0} / configured ${rights.configured || 0} / review ${rights.review_required || 0}</p>
            <p class="meta">重做队列：${rework.queued || 0}</p>
            <p class="meta">重做阻断：${(rework.rework_budget_summary && rework.rework_budget_summary.blocked) || 0}</p>
            <p class="meta">下次执行窗口：${scheduler.last_scheduler_run_id || "无"}</p>
          </article>
          <article class="item">
            <h3>循环策略 Top</h3>
            <p class="meta">失败Top：${failRows}</p>
            <p class="meta">下一归属Top：${nextAgentRows}</p>
          </article>
        </div>
      `;
    }

    function renderTasks() {
      const events = reworkHistory.events || [];
      const summary = reworkHistory.summary || {};
      const reworkPanel = events.length ? `
        <h2>返工历史</h2>
        <div class="grid">${events.slice(0, 12).map((event) => `
          <article class="item">
            <h3>${event.failure_code || "unknown"}</h3>
            <span class="status ${event.created_score_total >= 80 ? "good" : "warn"}">深度 ${event.rework_depth || 0}</span>
            <p class="meta">${event.source_work_id || event.source_task_id || "-"} → ${event.created_work_id || event.created_task_id || "-"}</p>
            <p class="meta">Agent ${event.target_agent || "-"} | Skill ${event.skill_id || "-"}</p>
            <p class="meta">根任务 ${event.root_task_id || "-"} | ${event.created_at || "-"}</p>
            <p class="meta">新评分 ${event.created_score_total ?? "-"} | 授权 ${event.created_rights_status || "-"}</p>
          </article>`).join("")}</div>` : `<p class="meta">暂无返工历史</p>`;
      $("tasks").innerHTML = `
        <div class="grid">${state.map((task) => `
        <article class="item">
          <h3>${task.work_id}</h3>
          <span class="status ${task.rights_status === "configured" ? "good" : "warn"}">${task.rights_status}</span>
          <p class="meta">${task.brief}</p>
          <p class="meta">候选 ${task.versions.length} | 选中 ${task.selected_version_id || "-"}</p>
          <p class="meta">父任务 ${task.parent_task_id || "-"} | 返工原因 ${task.rework_reason || "-"}</p>
          <p class="meta">返工深度 ${task.rework_depth || 0} | 历史 ${(task.rework_history || []).length}</p>
        </article>`).join("")}</div>
        <p class="meta">返工事件 ${summary.total_events || 0}</p>
        ${reworkPanel}`;
    }

    function renderWorks() {
      const versions = state.flatMap((task) => task.versions.map((version) => ({task, version})));
      $("works").innerHTML = `<div class="grid">${versions.map(({task, version}) => {
        const preview = version.export_files.find((f) => f.kind === "preview" && f.path);
        const files = version.export_files.filter((f) => f.ready && (f.path || f.download_url));
        return `<article class="item">
          <h3>${version.title}</h3>
          <p class="meta">${version.version_id} | ${version.status} | ${version.bpm || "-"} BPM | ${version.key || "-"}</p>
          <p class="meta">${((version.generation_route || {}).selection || {}).selected_provider_id || (version.generation_route || {}).provider || version.model_provider} | ${version.model_name || "-"}</p>
          ${preview ? `<audio controls src="${fileUrl(preview.path)}"></audio>` : ""}
          <div class="downloads">${files.map((f) => `<a href="${f.download_url || fileUrl(f.path)}" download>${f.kind}</a>`).join("")}</div>
          <p class="meta">任务 ${task.task_id}</p>
        </article>`;
      }).join("")}</div>`;
    }

    function renderScores() {
      const versions = state.flatMap((task) => task.versions.map((version) => ({task, version})));
      $("scores").innerHTML = `<div class="grid">${versions.map(({version}) => `
        <article class="item">
          <h3>${version.version_id}</h3>
          <span class="status ${(version.score_total || 0) >= 80 ? "good" : "bad"}">${version.score_total || 0}</span>
          <p class="meta">状态 ${version.status}</p>
          <pre>${JSON.stringify((version.generation_route || {}).selection || {}, null, 2) || "No generation route"}</pre>
          <pre>${Object.entries(version.score_breakdown || {}).map(([key, value]) => `${key}: ${value}`).join("\\n") || "No score breakdown"}</pre>
          <pre>${((version.audio_analysis || {}).technical_flags || []).join("\\n") || "No technical flags"}</pre>
          <pre>${(version.failure_codes || []).length ? version.failure_codes.join("\\n") : "No failure codes"}</pre>
        </article>`).join("")}</div>`;
    }

    function renderDelivery() {
      $("delivery").innerHTML = `<div class="grid">${state.map((task) => {
        const selected = task.versions.find((v) => v.version_id === task.selected_version_id) || task.versions[0];
        const master = selected ? selected.export_files.find((f) => f.kind === "master") : null;
        const licenses = selected ? selected.export_files.filter((f) => f.kind === "license_pack") : [];
        return `<article class="item">
          <h3>${task.work_id}</h3>
          <span class="status ${task.rights_status === "configured" ? "good" : "warn"}">${task.rights_status}</span>
          <p class="meta">master ${master && master.ready ? "ready" : "blocked"} ${master && master.blocked_reason ? "| " + master.blocked_reason : ""}</p>
          <div class="downloads">${licenses.map((f) => `<a href="${fileUrl(f.path)}" download>${f.kind}</a>`).join("")}</div>
          <div class="toolbar">
            <button onclick="configureRights('${task.task_id}')" ${task.rights_status === "configured" ? "disabled" : ""}>配置授权</button>
          </div>
        </article>`;
      }).join("")}</div>`;
    }

    load();
  </script>
</body>
</html>"""


def render_workbench_html() -> str:
    return INDEX_HTML


def _version_loop_state(task: dict[str, Any], version: dict[str, Any]) -> dict[str, Any]:
    version_id = version.get("version_id")
    failure_codes = version.get("failure_codes", [])
    handoffs: list[dict[str, Any]] = []

    for failure_code in failure_codes:
        rule = get_rework_rule(failure_code)
        if rule is None:
            handoffs.append(
                {
                    "failure_code": failure_code,
                    "target_agent": "Rework Orchestrator",
                    "target_skill": "loop_rework",
                    "action": "inspect and define a repair plan",
                    "auto_rework_allowed": False,
                    "requires_human_review": True,
                    "delivery_block_only": False,
                }
            )
            continue
        handoffs.append(
            {
                "failure_code": failure_code,
                "target_agent": rule.target_agent,
                "target_skill": rule.skill_id,
                "action": rule.action,
                "auto_rework_allowed": rule.auto_rework_allowed,
                "requires_human_review": rule.requires_human_review,
                "delivery_block_only": rule.delivery_block_only,
                "preserve_fields": list(rule.preserve_fields),
                "mutable_fields": list(rule.mutable_fields),
                "retry_budget": rule.retry_budget,
            }
        )

    if handoffs:
        primary = handoffs[0]
        loop_stage = "human_review_required" if primary["requires_human_review"] else "auto_rework"
        if primary["delivery_block_only"] and task.get("rights_status") == "missing":
            loop_stage = "rights_blocked"
            next_agent = "Rights Configurator"
            next_action = "configure rights before delivery"
        else:
            next_agent = primary["target_agent"]
            next_action = primary["action"]
    elif task.get("rights_status") == "missing":
        loop_stage = "delivery_blocked"
        next_agent = "Rights Configurator"
        next_action = "configure rights package first"
    elif version.get("status") == "qa_fail":
        loop_stage = "rework_decide"
        next_agent = "Rework Orchestrator"
        next_action = "decide targeted rework"
    else:
        loop_stage = "ready_for_packaging"
        next_agent = "Delivery Packager"
        next_action = "create delivery package after final QA"

    hard_gate_pass = version.get("status") == "qa_pass" and not failure_codes
    return {
        "version_id": version_id,
        "failure_codes": failure_codes,
        "rework_targets": handoffs,
        "next_agent": next_agent,
        "next_action": next_action,
        "decision": loop_stage,
        "hard_gate_pass": bool(hard_gate_pass),
        "score_total": version.get("score_total"),
    }


def _decorate_task(task: dict[str, Any]) -> dict[str, Any]:
    task_copy = dict(task)
    versions = []
    for version in task_copy.get("versions", []):
        version_copy = dict(version)
        version_copy["loop_state"] = _version_loop_state(task_copy, version_copy)
        versions.append(version_copy)
    task_copy["versions"] = versions
    return task_copy


def _ops_report(workspace: Path, repository: ResultRepository, scheduler: DailyAutomationScheduler, automation: DailyAutomationService) -> dict[str, Any]:
    tasks = repository.list_results()
    decorated = [_decorate_task(task) for task in tasks]
    version_count = sum(len(task.get("versions", [])) for task in tasks)
    fail_count = sum(1 for task in decorated for version in task.get("versions", []) if (version.get("score_total") or 0) < 80 or version.get("failure_codes"))
    pass_count = max(0, version_count - fail_count)
    failure_counter: Counter[str] = Counter()
    agent_counter: Counter[str] = Counter()
    score_values: list[int] = []
    for task in decorated:
        for version in task.get("versions", []):
            score = int(version.get("score_total") or 0)
            score_values.append(score)
            for failure_code in version.get("failure_codes", []):
                failure_counter[str(failure_code)] += 1
            next_agent = (version.get("loop_state") or {}).get("next_agent")
            if next_agent:
                agent_counter[next_agent] += 1

    rework_queue = automation.build_rework_queue()
    rework_queue_summary = automation._rework_budget_summary()
    latest_daily = automation.latest_daily_reports()[:1]
    scheduler_state_path = workspace / "scheduler" / "state.json"
    scheduler_state: dict[str, Any] = {}
    if scheduler_state_path.exists():
        with scheduler_state_path.open("r", encoding="utf-8") as handle:
            scheduler_state = json.load(handle)

    return {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "task_count": len(tasks),
        "version_count": version_count,
        "rights_status": {
            "missing": sum(1 for task in tasks if task.get("rights_status") == "missing"),
            "configured": sum(1 for task in tasks if task.get("rights_status") == "configured"),
            "review_required": sum(1 for task in tasks if task.get("rights_status") not in {"missing", "configured"}),
        },
        "quality": {
            "version_pass": pass_count,
            "version_fail": fail_count,
            "qa_pass_rate": round(pass_count / version_count * 100, 2) if version_count else 0.0,
            "average_score": round(sum(score_values) / len(score_values), 2) if score_values else 0.0,
            "failure_counts": dict(failure_counter.most_common()),
            "next_agent_counts": dict(agent_counter.most_common()),
        },
        "rework": {
            "total_events": ResultRepository(workspace).rework_history()["summary"]["total_events"],
            "queued": len(rework_queue),
            "rework_budget_summary": rework_queue_summary,
        },
        "latest_daily_reports": latest_daily,
        "scheduler_state": scheduler_state,
    }


def make_handler(workspace: Path | str):
    workspace_path = Path(workspace)
    engine = CreationEngine(workspace_path)
    repository = ResultRepository(workspace_path)
    automation = DailyAutomationService(workspace_path)
    scheduler = DailyAutomationScheduler(workspace_path)

    class MusicWorkbenchHandler(BaseHTTPRequestHandler):
        server_version = "MusicWorkbench/0.1"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(render_workbench_html())
            elif parsed.path == "/api/tasks":
                tasks = [_decorate_task(task) for task in repository.list_results()]
                self._send_json(tasks)
            elif parsed.path == "/api/rework-history":
                self._send_json(repository.rework_history())
            elif parsed.path == "/api/skills":
                self._send_json(skills_snapshot())
            elif parsed.path == "/api/ops":
                self._send_json(_ops_report(workspace_path, repository, scheduler, automation))
            elif parsed.path == "/files":
                params = parse_qs(parsed.query)
                self._send_file(params.get("path", [""])[0])
            else:
                self.send_error(404, "not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/create":
                    payload = self._read_json()
                    request = MusicCreationRequest(**payload)
                    result = engine.create(request, candidate_count=3)
                    self._send_json(result.to_dict(), status=201)
                elif parsed.path == "/api/import-url":
                    payload = self._read_json()
                    request = MusicCreationRequest(**payload["request"])
                    result = engine.import_external_download(
                        request,
                        download_url=payload["url"],
                        duration_sec=float(payload["duration_sec"]),
                        candidate_count=3,
                    )
                    self._send_json(result.to_dict(), status=201)
                elif parsed.path == "/api/automation/daily":
                    report = automation.create_daily_batch(target_count=10, candidate_count=3)
                    self._send_json(report, status=201)
                elif parsed.path == "/api/automation/rework":
                    report = automation.run_rework_queue(limit=5)
                    self._send_json(report, status=201)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/manual-rework"):
                    task_id = parsed.path.split("/")[3]
                    payload = self._read_json()
                    report = automation.run_manual_rework(
                        task_id=task_id,
                        version_id=payload.get("version_id"),
                        failure_code=payload.get("failure_code") or "WEAK_HOOK",
                        notes=payload.get("notes") or "",
                    )
                    self._send_json(report, status=201)
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/configure-rights"):
                    task_id = parsed.path.split("/")[3]
                    result = repository.get_result(task_id)
                    if result is None:
                        self.send_error(404, "task not found")
                        return
                    payload = self._read_json()
                    configured = _configure_rights_from_dict(engine, result, payload)
                    self._send_json(configured.to_dict())
                elif parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/delivery-package"):
                    task_id = parsed.path.split("/")[3]
                    result = repository.get_result(task_id)
                    if result is None:
                        self.send_error(404, "task not found")
                        return
                    restored = result_from_dict(result)
                    export = engine.create_delivery_package(restored)
                    self._send_json({"task_id": restored.task_id, "version_id": export.version_id, "delivery_package": export.path}, status=201)
                else:
                    self.send_error(404, "not found")
            except Exception as exc:
                self.send_error(400, str(exc))

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8") or "{}")

        def _send_json(self, payload: Any, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_html(self, html: str) -> None:
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_file(self, raw_path: str) -> None:
            if not raw_path:
                self.send_error(400, "path required")
                return
            candidate = Path(unquote(raw_path))
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            resolved = candidate.resolve()
            cwd = Path.cwd().resolve()
            workspace_resolved = workspace_path.resolve()
            if not (str(resolved).startswith(str(cwd)) or str(resolved).startswith(str(workspace_resolved))):
                self.send_error(403, "path outside workspace")
                return
            if not resolved.exists() or not resolved.is_file():
                self.send_error(404, "file not found")
                return
            content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
            data = resolved.read_bytes()
            self.send_response(200)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return MusicWorkbenchHandler


def _configure_rights_from_dict(engine: CreationEngine, result: dict[str, Any], payload: dict[str, Any] | None = None):
    payload = payload or {}
    restored = result_from_dict(result)
    return engine.configure_rights(
        restored,
        RightsConfiguration(
            rights_owner="Internal AI Music Lab",
            usage_scope="internal demo and production validation",
            territory="worldwide",
            duration="perpetual",
            ai_disclosure="Generated by AI music production engine MVP with human-directed prompt and QA.",
            model_license="internal mock generator; replace with real model license before commercial delivery",
            commercial_use_allowed=False,
            platform_profile_id=payload.get("platform_profile_id") or "internal_export",
            export_profile=payload.get("export_profile") or "wav_master_preview_license",
            manual_approval_required=bool(payload.get("manual_approval_required", False)),
            reference_sources=list(payload.get("reference_sources", [])),
            notes="Configured from workbench.",
        ),
    )


def run_server(host: str, port: int, workspace: Path | str) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), make_handler(workspace))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="AI music production workbench")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--workspace", default="runs\\web")
    args = parser.parse_args()
    server = run_server(args.host, args.port, args.workspace)
    print(f"AI music workbench running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
