export const statusLabels = {
  selected: "已选定",
  qa_pass: "评分通过",
  qa_fail: "需要返工",
  generated: "已生成",
  edited: "已编辑",
  processed: "已处理",
  rework: "返工中"
};

export const loopDecisionLabels = {
  pass: "可通过",
  rework: "需要重构",
  human_review: "需要人工打回",
  delivery_blocked: "发布前处理",
  human_review_required: "需要人工打回",
  auto_rework: "需要重构",
  rights_blocked: "发布前处理",
  rework_decide: "需要重构",
  ready_for_packaging: "可通过"
};

export const sortFieldLabels = {
  generatedAt: "创作时间",
  score_total: "最高评分",
  title: "标题"
};

export const rightsLabels = {
  missing: "待配置",
  configured: "已配置",
  review_required: "需复核",
  blocked: "已阻断"
};

export const exportLabels = {
  master: "完整版本",
  license_pack: "发布资料",
  delivery_package: "发布任务包"
};

export const languageLabels = {
  zh: "中文",
  en: "英文",
  ja: "日文",
  ko: "韩文",
  none: "纯音乐"
};

export const genreLabels = {
  "Pop": "流行 Pop",
  "Mandarin Pop": "华语流行 Mandarin Pop",
  "R&B": "节奏布鲁斯 R&B",
  "Rock": "摇滚 Rock",
  "Folk": "民谣 Folk",
  "Electronic": "电子 Electronic",
  "House": "浩室 House",
  "Future Bass": "未来贝斯 Future Bass",
  "City Pop": "城市流行 City Pop",
  "Hip-Hop": "说唱 Hip-Hop",
  "Trap": "陷阱 Trap",
  "Lo-fi": "低保真 Lo-fi",
  "Cinematic": "影视感 Cinematic",
  "Piano Ballad": "钢琴抒情 Piano Ballad",
  "Acoustic": "原声 Acoustic",
  "Chinese Fusion": "国风 Chinese Fusion",
  "Ancient Style": "古风 Ancient Style",
  "Game Music": "游戏配乐 Game Music",
  "Ambient": "冥想氛围 Ambient",
  "Corporate": "企业宣传 Corporate",
  "Short Video BGM": "短视频 BGM Short Video BGM"
};

export const toneLabels = {
  warm: "温暖",
  lonely: "孤独",
  relieved: "释然",
  passionate: "热血",
  romantic: "浪漫",
  oppressed: "压抑",
  dreamy: "梦幻",
  firm: "坚定",
  broken: "破碎感",
  reborn: "重生感",
  cityNight: "城市夜晚",
  youth: "少年感",
  cinematic: "电影感",
  chinese: "国风感",
  cyber: "赛博感",
  healing: "治愈感"
};

export const secondaryToneLabels = {
  gentle: "温柔",
  restrained: "克制",
  bright: "明亮",
  dark: "黑暗",
  light: "轻快",
  steady: "沉稳",
  nostalgic: "怀念",
  hopeful: "希望",
  unwilling: "不甘",
  calm: "平静",
  explosive: "爆发",
  mysterious: "神秘",
  airy: "空灵",
  relaxed: "松弛",
  tense: "紧张"
};

export const agentLabels = {
  "Brief Parser": "创作策划 Agent",
  "Melody Composer": "编曲 Agent",
  "Lyric Editor": "歌词 Agent",
  "Audio Analyzer": "音频检查 Agent",
  "Originality Guard": "原创安全 Agent",
  "Rework Orchestrator": "返工调度 Agent",
  "Rights Configurator": "发布配置 Agent",
  "Delivery Packager": "发布任务 Agent"
};

export const failureLabels = {
  BAD_DURATION: "结构过短",
  STRUCTURE_TOO_SHORT: "结构过短",
  LYRIC_TOO_SHORT: "歌词太短",
  LYRIC_MISSING: "歌词太短",
  WEAK_HOOK: "Hook 弱",
  EMOTION_MISMATCH: "情绪不匹配",
  ARRANGEMENT_EMPTY: "编曲空洞",
  DUPLICATE_CANDIDATE: "候选重复",
  ORIGINALITY_REVIEW_REQUIRED: "需要人工打回",
  AUDIENCE_MISMATCH: "情绪不匹配",
  TECHNICAL_AUDIO_FAIL: "需要重构",
  RIGHTS_MISSING: "发布前处理",
  mock_file_internal_validation: "发布前处理",
  rights_status_missing: "发布前处理",
  quality_failure: "需要重构"
};

export const scoreLabels = {
  audio_quality: "音频质量",
  melody_quality: "旋律",
  catchiness: "Hook",
  structure_integrity: "结构",
  arrangement_fit: "编曲",
  lyric_singability: "歌词",
  audience_fit: "受众",
  originality_safety: "原创安全",
  delivery_readiness: "发布准备"
};
