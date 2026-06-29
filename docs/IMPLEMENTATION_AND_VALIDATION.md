# AI 音乐制作系统分步实现与校验计划

## 0. 相关规格

本文件只覆盖网站工作台 MVP 的实现与校验。第一阶段应先实现 AI 音乐创作引擎，见 [AI_CREATION_ENGINE_SPEC.md](AI_CREATION_ENGINE_SPEC.md)。更完整的分工、Skills、LOOP 和验收规则见：

- [OPEN_SOURCE_SKILLS_ABSORPTION.md](OPEN_SOURCE_SKILLS_ABSORPTION.md)
- [AGENT_WORK_BREAKDOWN.md](AGENT_WORK_BREAKDOWN.md)
- [LOOP_STATE_MACHINE.md](LOOP_STATE_MACHINE.md)
- [QUALITY_ACCEPTANCE_SYSTEM.md](QUALITY_ACCEPTANCE_SYSTEM.md)
- [PHASED_EXECUTION_PLAN.md](PHASED_EXECUTION_PLAN.md)

## 1. 当前阶段目标

当前文档描述网站工作台 MVP。它应承载已经存在的 AI 音乐创作引擎，而不是替代创作引擎。

验收目标：

- 网站能打开。
- 页面能看到 `每日任务`。
- 页面能看到 `作品库`。
- 页面能看到 `评分中心`。
- 页面能看到 `交付与授权中心`。
- 页面表达的是音乐制作流程，不是音乐分发平台。

## 2. 分步计划

### Step 1: 项目骨架

实施：

- 创建前端应用。
- 建立统一布局。
- 建立导航。
- 准备 mock 数据。

页面入口：

- 每日任务
- 作品库
- 评分中心
- 交付与授权中心

校验：

- 本地开发服务器能启动。
- 浏览器打开后不白屏。
- 四个导航入口可见。
- 点击导航不会 404。

### Step 2: 每日任务页面

实施：

- 展示每日自动制作任务。
- 任务数量模拟 10-20 条。
- 每条任务展示制作状态和 LOOP 状态。

建议字段：

- 任务名
- 风格
- 目标用途
- 受众
- 当前阶段
- 版本数量
- 返工次数
- QA 状态
- 授权状态
- 下一个 Agent

校验：

- 页面能看出这是音乐制作任务，不是普通待办。
- 能看到自动化 LOOP 状态。
- 能看到至少 10 条任务样例。

### Step 3: 作品库页面

实施：

- 展示制作中的音乐资产。
- 展示每首作品的版本、阶段、评分和文件状态。

建议字段：

- 作品名
- 风格
- BPM
- 调式
- 版本
- 制作阶段
- 最高评分
- 文件状态
- 最近更新时间

校验：

- 页面表达为制作资产库，不是歌单平台。
- 能看到草稿、待评分、返工中、已母带、可交付等状态。
- 每个作品能关联到制作任务或版本。

### Step 4: 评分中心页面

实施：

- 展示待评分作品。
- 展示质量维度、权重、得分和返工建议。
- 区分硬性门槛和加权评分。

建议维度：

- 听感与音频质量
- 旋律质量
- 朗朗上口
- 结构完整度
- 编曲与音色
- 歌词与可唱性
- 受众匹配
- 原创与安全
- 制作交付完整性

校验：

- 页面能看到每首作品为什么通过或失败。
- 低分作品能看到返工原因。
- 高风险作品不能显示为可交付。

### Step 5: 交付与授权中心页面

实施：

- 展示交付包。
- 展示授权配置。
- 展示导出规格。
- 展示可选平台连接配置状态。

建议字段：

- 交付包名
- 关联作品
- 版本
- 包内容
- 授权模板
- 授权主体
- 使用范围
- AI 声明
- 导出规格
- 可选连接配置
- 导出状态

明确不做：

- 音乐社区
- 用户主页
- 粉丝关系
- 点赞评论
- 推荐流
- 公开播放平台

校验：

- 页面名称和内容体现交付、导出、授权配置。
- 不出现社区、榜单、粉丝、评论、点赞等平台功能。
- 授权未配置完整的作品不能显示为可直接交付。

### Step 6: LOOP 状态和 mock 数据

实施：

- 用 mock 数据模拟完整状态流。
- 四个页面使用同一批 mock 数据，避免页面各说各话。

状态建议：

```text
CREATED
BRIEF_READY
COMPOSITION_READY
GENERATING
VERSIONS_READY
AUDIO_QA_PASS
AUDIO_QA_FAIL
ORIGINALITY_PASS
ORIGINALITY_REWORK
REWORK_PENDING
REWORKING
SELECTED
MIXING
MASTERED
FINAL_QA_PASS
STORED
DELIVERY_PACKAGE_READY
HUMAN_REVIEW_REQUIRED
REJECTED
```

校验：

- 每日任务能展示状态。
- 作品库能展示版本和阶段。
- 评分中心能展示失败原因。
- 交付与授权中心能展示授权和导出状态。

### Step 7: 自动化任务设计

实施：

- 第一阶段先做 mock 的每日任务生成结果。
- 后续接入真实定时任务。

真实调度目标：

```text
每天创建 10-20 条制作任务
每条任务生成 3-5 个候选版本
每个版本完成 QA
低分版本自动返工
高分版本进入混音母带
通过最终 QA 后入库
授权配置完整后生成交付包
```

校验：

- 文档和数据结构能支持定时任务。
- 页面能展示自动化生产结果。
- 不需要人工逐条点击生成才能理解流程。

## 3. 首版数据模型

### 3.1 ProductionTask

```ts
type ProductionTask = {
  id: string;
  title: string;
  genre: string;
  audience: string;
  useCase: string;
  status: string;
  nextAgent: string;
  versionCount: number;
  reworkCount: number;
  qaStatus: "pending" | "pass" | "fail" | "review";
  authStatus: "not_required" | "missing" | "configured" | "review";
};
```

### 3.2 MusicWork

```ts
type MusicWork = {
  id: string;
  title: string;
  genre: string;
  bpm: number;
  key: string;
  stage: string;
  bestScore: number;
  version: string;
  assetStatus: string;
  updatedAt: string;
};
```

### 3.3 QualityReview

```ts
type QualityReview = {
  id: string;
  workId: string;
  workTitle: string;
  totalScore: number;
  hardGatePass: boolean;
  melodyScore: number;
  catchyScore: number;
  arrangementScore: number;
  lyricScore: number;
  audienceFitScore: number;
  originalityScore: number;
  decision: "approve" | "rework" | "reject" | "human_review";
  reworkReason: string;
};
```

### 3.4 DeliveryPackage

```ts
type DeliveryPackage = {
  id: string;
  name: string;
  workId: string;
  workTitle: string;
  version: string;
  contents: string[];
  usageScope: string;
  rightsOwner: string;
  aiDisclosure: string;
  exportFormat: string[];
  authStatus: "missing" | "configured" | "review_required";
  exportStatus: "blocked" | "ready" | "exporting" | "done";
};
```

## 4. 验收检查表

### 4.1 网站可访问

- [ ] 开发服务器能启动。
- [ ] 浏览器能打开本地地址。
- [ ] 页面不白屏。
- [ ] 控制台没有关键运行时错误。

### 4.2 页面结构

- [ ] 能看到每日任务。
- [ ] 能看到作品库。
- [ ] 能看到评分中心。
- [ ] 能看到交付与授权中心。
- [ ] 四个入口都能点击。

### 4.3 音乐制作定位

- [ ] 每日任务展示音乐制作任务。
- [ ] 作品库展示音乐资产和版本。
- [ ] 评分中心展示制作质量验收。
- [ ] 交付与授权中心展示导出包和授权配置。
- [ ] 页面没有做成音乐社区或分发平台。

### 4.4 LOOP 可见

- [ ] 能看到任务当前阶段。
- [ ] 能看到返工次数。
- [ ] 能看到 QA 状态。
- [ ] 能看到失败原因。
- [ ] 能看到下一个负责 Agent。

### 4.5 交付授权

- [ ] 能看到授权主体。
- [ ] 能看到使用范围。
- [ ] 能看到 AI 声明。
- [ ] 能看到导出规格。
- [ ] 授权缺失时不能显示为可交付。

## 5. 校验命令

具体命令以实际技术栈为准。

如果使用 Vite / React / TypeScript：

```powershell
npm install
npm run dev
npm run build
```

如果配置了 lint 和测试：

```powershell
npm run lint
npm run typecheck
npm test
```

如果使用 pnpm：

```powershell
pnpm install
pnpm dev
pnpm build
pnpm lint
pnpm typecheck
pnpm test
```

## 6. 通过标准

第一阶段通过标准：

- `npm run build` 或对应构建命令通过。
- 本地网站可以打开。
- 首页或导航清晰展示四个工作区。
- 页面内容围绕音乐制作、质量验收、LOOP 返工、交付授权。
- 没有把系统表达成音乐分发平台。

## 7. 后续阶段

第一阶段完成后再进入：

1. 真实后端 API。
2. 数据库持久化。
3. 定时任务调度。
4. 真实模型适配。
5. 音频分析工具接入。
6. 原创性检测。
7. 自动返工策略。
8. 授权配置和导出包真实落盘。
9. 可选外部平台连接。
