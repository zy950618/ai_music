export function AppHeader() {
  return `<header class="app-header">
    <div class="brand-block">
      <div class="logo-mark" aria-hidden="true">音</div>
      <div>
        <h1>AI 音乐工坊</h1>
        <p id="moduleTitle" class="module-title">生产总览</p>
      </div>
    </div>
    <div class="header-actions">
      <div class="theme-tools" aria-label="主题切换">
        <button type="button" class="icon-button" data-action="theme-mode" title="切换浅色/深色">◐</button>
        <button type="button" class="swatch teal" data-theme-color="teal" title="青绿主题"></button>
        <button type="button" class="swatch blue" data-theme-color="blue" title="蓝色主题"></button>
        <button type="button" class="swatch purple" data-theme-color="purple" title="紫色主题"></button>
        <button type="button" class="swatch orange" data-theme-color="orange" title="橙色主题"></button>
        <button type="button" class="swatch graphite" data-theme-color="graphite" title="灰黑主题"></button>
      </div>
      <div id="userBadge" class="user-badge hidden">
        <span id="userAvatar" class="avatar"></span>
        <span id="userName"></span>
        <button type="button" class="secondary small" data-action="logout">退出</button>
      </div>
    </div>
  </header>`;
}
