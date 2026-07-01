export function createWorkbenchState() {
  const savedUserId = localStorage.getItem("aiMusicWorkbench.userId") || "";
  const savedTheme = JSON.parse(localStorage.getItem("aiMusicWorkbench.theme") || "null") || {
    mode: "light",
    color: "teal"
  };
  const users = [
    { id: "creator_a", workspace_id: "workspace_creator_a", name: "林舟", avatar: "林", role: "创作者" },
    { id: "reviewer_b", workspace_id: "workspace_reviewer_b", name: "许言", avatar: "许", role: "审核者" },
    { id: "admin_c", workspace_id: "workspace_admin_c", name: "沈岚", avatar: "沈", role: "管理员" }
  ];
  return {
    users,
    currentUser: users.find((user) => user.id === savedUserId) || null,
    theme: savedTheme,
    currentModule: "生产总览",
    publishTasks: [],
    platformConfigs: defaultPlatformConfigs()
  };
}

export function defaultPlatformConfigs() {
  return [
    { platform: "抖音", enabled: true, account: "douyin_music_ops", credential: "已保存占位", titleTemplate: "{title} - AI 音乐工坊", tags: "AI音乐,原创音乐", statement: "AI 辅助制作，人工审核", format: "竖版视频 + WAV", lastVerifiedAt: "2026-06-30", status: "可发布" },
    { platform: "B站", enabled: true, account: "bilibili_creator", credential: "已保存占位", titleTemplate: "原创音乐 | {title}", tags: "原创,音乐制作", statement: "AI 辅助制作，保留人工审核记录", format: "横版视频 + WAV", lastVerifiedAt: "2026-06-30", status: "可发布" },
    { platform: "网易云", enabled: false, account: "待填写", credential: "API Key / Cookie 占位", titleTemplate: "{title}", tags: "原创音乐", statement: "发布前补充平台声明", format: "WAV Master", lastVerifiedAt: "-", status: "未配置" },
    { platform: "YouTube", enabled: false, account: "待填写", credential: "OAuth 占位", titleTemplate: "{title} | AI Music Workshop", tags: "AI music, original", statement: "AI assisted music production", format: "Video + WAV", lastVerifiedAt: "-", status: "未配置" }
  ];
}
