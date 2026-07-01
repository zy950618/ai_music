import { genreLabels, secondaryToneLabels, toneLabels } from "../ui/labels.js";
import { escapeHtml, labelOf } from "../ui/helpers.js";
import { workbenchApi } from "../services/workbench-api.js";

const primaryToneKeys = Object.keys(toneLabels);
const secondaryToneKeys = Object.keys(secondaryToneLabels);

const soundDesigns = [
  {
    id: "piano_ballad",
    name: "钢琴抒情版",
    instruments: ["钢琴", "弦乐", "轻鼓", "Pad"],
    vocal_type: "温暖男声",
    mood_tags: ["温暖", "释然", "希望"],
    arrangement_direction: "主歌克制，副歌增加弦乐和鼓组，尾段留出情绪释放。",
    fit_score: 94,
    reason: "适合完整歌曲，容易承接城市夜晚和重生感主题。"
  },
  {
    id: "electronic_air",
    name: "电子氛围版",
    instruments: ["合成器", "电子鼓", "低频贝斯", "Texture"],
    vocal_type: "低语男声",
    mood_tags: ["梦幻", "城市夜晚", "空灵"],
    arrangement_direction: "用电子纹理铺底，副歌抬高能量，适合短视频和夜景画面。",
    fit_score: 89,
    reason: "适合有赛博感或城市感的主题，候选差异明显。"
  },
  {
    id: "drum_plus",
    name: "鼓组增强版",
    instruments: ["鼓组", "贝斯", "电吉他", "钢琴"],
    vocal_type: "明亮女声",
    mood_tags: ["坚定", "爆发", "热血"],
    arrangement_direction: "保留抒情主线，副歌加入更强鼓组推动。",
    fit_score: 86,
    reason: "适合需要更强记忆点和段落推进的作品。"
  }
];

export function buildCreationPayload(form, currentUser = null) {
  const primaryTone = String(form.get("primaryTone") || "warm");
  const secondaryTone = String(form.get("secondaryTone") || "hopeful");
  const selectedDesign = pickSoundDesign(form);
  const genre = String(form.get("genre") || "Mandarin Pop");
  return {
    workspace_id: currentUser?.workspace_id || "workspace_guest",
    title: form.get("title"),
    mode: "song",
    language: "zh",
    languages: ["zh"],
    theme: form.get("theme"),
    category: labelOf(toneLabels, primaryTone),
    categories: [labelOf(toneLabels, primaryTone)],
    mood: [labelOf(toneLabels, primaryTone), labelOf(secondaryToneLabels, secondaryTone)],
    emotions: [labelOf(toneLabels, primaryTone), labelOf(secondaryToneLabels, secondaryTone)],
    genre: [genre],
    scenes: [String(form.get("use_case") || "完整歌曲")],
    instruments: selectedDesign.instruments,
    vocal_types: [selectedDesign.vocal_type],
    audience: "音乐创作者",
    use_case: form.get("use_case"),
    duration_sec: Number(form.get("duration_sec") || 180),
    bpm: 96,
    key: "C",
    candidate_count: Math.min(5, Math.max(3, Number(form.get("candidate_count") || 3))),
    vocal_required: true,
    voice_profile: selectedDesign.vocal_type,
    forbidden: ["未授权声线克隆", "真实歌曲复刻"],
    export_formats: ["wav"],
    sound_design: selectedDesign
  };
}

export function createCreationController({load, root = document, api = workbenchApi, getCurrentUser = () => null} = {}) {
  const $ = (id) => root.getElementById(id);

  function mount() {
    renderChoices();
    renderSuggestions();
    const form = $("createForm");
    form.addEventListener("change", (event) => {
      if (event.target.name === "primaryTone" || event.target.name === "secondaryTone" || event.target.name === "use_case") {
        renderSuggestions();
      }
    });
    form.addEventListener("submit", handleSubmit);
  }

  function renderChoices() {
    renderChoiceGroup("primaryTone", primaryToneKeys, toneLabels, "warm");
    renderChoiceGroup("secondaryTone", secondaryToneKeys, secondaryToneLabels, "hopeful");
  }

  function renderChoiceGroup(name, keys, labels, defaultValue) {
    const host = root.querySelector(`[data-choice-group="${name}"]`);
    host.innerHTML = keys.map((key) => `<label class="chip-choice">
      <input type="radio" name="${name}" value="${key}" ${key === defaultValue ? "checked" : ""}>
      <span>${escapeHtml(labels[key])}</span>
    </label>`).join("");
  }

  function renderSuggestions() {
    const host = $("soundSuggestions");
    host.innerHTML = soundDesigns.map((item, index) => `<label class="suggestion-card">
      <input type="radio" name="sound_design_choice" value="${item.id}" ${index === 0 ? "checked" : ""}>
      <strong>${item.name}</strong>
      <span class="score-pill">${item.fit_score}</span>
      <span>${item.instruments.join("、")}</span>
      <span>${item.vocal_type}</span>
      <span>${item.arrangement_direction}</span>
      <em>${item.reason}</em>
    </label>`).join("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = buildCreationPayload(form, getCurrentUser());
    setStatus(`正在生成 ${payload.candidate_count} 个候选...`);
    try {
      const response = form.get("async_generation") === "on"
        ? await api.createAsync(payload)
        : await api.create(payload);
      if (!response.ok) {
        setStatus(await response.text());
        return;
      }
      const created = await response.json();
      if (created.job_id) {
        await pollGenerationJob(created.job_id);
      } else {
        await load();
        setStatus("候选已生成，作品库已刷新。");
      }
    } catch (error) {
      setStatus(`创建失败: ${error.message || error}`);
    }
  }

  async function pollGenerationJob(jobId) {
    for (let attempt = 0; attempt < 160; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const response = await api.job(jobId);
      const job = await response.json();
      setStatus(`后台生成状态: ${job.status_label_zh || job.status}`);
      if (job.status === "completed") {
        await load();
        setStatus("候选已生成，作品库已刷新。");
        return;
      }
      if (job.status === "failed") {
        setStatus(`生成失败: ${job.error || jobId}`);
        return;
      }
    }
    setStatus(`后台任务仍在运行: ${jobId}`);
  }

  function pickSoundDesign(form) {
    const selected = String(form.get("sound_design_choice") || "");
    return soundDesigns.find((item) => item.id === selected) || soundDesigns[0];
  }

  function setStatus(message) {
    const node = $("formStatus");
    if (node) node.textContent = message;
  }

  return {mount, buildCreationPayload, pollGenerationJob};
}

export { soundDesigns, genreLabels };
