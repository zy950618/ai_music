export function CreationPanel() {
  return `<div class="creation-workspace">
    <form id="createForm" class="creation-form">
      <div class="section-title">
        <div>
          <h2>新建创作</h2>
          <p class="meta">按主题、主基调、副基调和用途生成 2-3 套声音设计方案，再生成候选。</p>
        </div>
      </div>
      <div class="flow-steps">
        <section class="form-step">
          <h3>Step 1 写主题</h3>
          <label>作品标题</label>
          <input name="title" value="城市夜晚的新歌">
          <label>想表达什么</label>
          <textarea name="theme">城市夜晚里，一个人从低落走向重新开始</textarea>
        </section>
        <section class="form-step">
          <h3>Step 2 选择主基调</h3>
          <div class="choice-grid" data-choice-group="primaryTone"></div>
        </section>
        <section class="form-step">
          <h3>Step 3 选择副基调</h3>
          <div class="choice-grid" data-choice-group="secondaryTone"></div>
        </section>
        <section class="form-step">
          <h3>Step 4 选择用途</h3>
          <select name="use_case">
            <option value="完整歌曲">完整歌曲</option>
            <option value="短视频 BGM">短视频 BGM</option>
            <option value="影视感片段">影视感片段</option>
            <option value="游戏配乐">游戏配乐</option>
            <option value="企业宣传">企业宣传</option>
          </select>
          <label>风格</label>
          <select name="genre">
            <option value="Pop">流行 Pop</option>
            <option value="Mandarin Pop" selected>华语流行 Mandarin Pop</option>
            <option value="R&B">节奏布鲁斯 R&B</option>
            <option value="Rock">摇滚 Rock</option>
            <option value="Folk">民谣 Folk</option>
            <option value="Electronic">电子 Electronic</option>
            <option value="House">浩室 House</option>
            <option value="Future Bass">未来贝斯 Future Bass</option>
            <option value="City Pop">城市流行 City Pop</option>
            <option value="Hip-Hop">说唱 Hip-Hop</option>
            <option value="Trap">陷阱 Trap</option>
            <option value="Lo-fi">低保真 Lo-fi</option>
            <option value="Cinematic">影视感 Cinematic</option>
            <option value="Piano Ballad">钢琴抒情 Piano Ballad</option>
            <option value="Acoustic">原声 Acoustic</option>
            <option value="Chinese Fusion">国风 Chinese Fusion</option>
            <option value="Ancient Style">古风 Ancient Style</option>
            <option value="Game Music">游戏配乐 Game Music</option>
            <option value="Ambient">冥想氛围 Ambient</option>
            <option value="Corporate">企业宣传 Corporate</option>
            <option value="Short Video BGM">短视频 BGM Short Video BGM</option>
          </select>
          <label>完整版本时长</label>
          <input name="duration_sec" type="number" min="180" max="300" value="180">
        </section>
        <section class="form-step wide-step">
          <h3>Step 5 系统推荐声音设计</h3>
          <div id="soundSuggestions" class="suggestion-grid"></div>
        </section>
        <section class="form-step wide-step">
          <h3>Step 6 选择方案</h3>
          <p class="meta">未手动选择时，系统自动采用 fit_score 最高的方案。</p>
          <input type="hidden" name="sound_design_id" value="">
          <label>候选数量</label>
          <select name="candidate_count">
            <option value="3" selected>生成 3 个候选</option>
            <option value="4">生成 4 个候选</option>
            <option value="5">生成 5 个候选</option>
          </select>
          <label class="inline-check">
            <input name="async_generation" type="checkbox" checked>
            后台生成
          </label>
          <div class="toolbar">
            <button type="submit" id="createBtn">生成候选</button>
          </div>
          <p id="formStatus" class="meta"></p>
        </section>
      </div>
    </form>
  </div>`;
}
