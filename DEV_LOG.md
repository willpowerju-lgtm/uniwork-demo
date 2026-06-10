# Uniwork 开发日志 · 2026-06-10

单文件 AI 投研工作台，一天内从「能跑的 demo」迭代到「带工具 harness + 逐条批阅 + 持久化」的可分享版本。本日志记录**架构设计 / 核心实现 / 主要 bug**。

---

## 一、整体架构

```
单文件 index.html（Vue 3 global build + 全 CDN，零构建）
  ├─ 文档：TipTap(ProseMirror) + mammoth(docx→html) + docx-preview(高保真) + html-docx-js(导出) + turndown
  ├─ 表格：Luckysheet + LuckyExcel(xlsx) + SheetJS(csv 桥接/导出)
  ├─ AI  ：DeepSeek V4（OpenAI 兼容）—— 流式 ReAct：reasoning_content(COT) + 原生 function calling
  ├─ 存储：IndexedDB（文件二进制 / 会话 / UI 状态）
  └─ 浏览器直连 api.deepseek.com（CORS 放行；Key 存 config.local.js 或 localStorage）
        │
        ▼  规避 CORS / 跑 Python 库
server.py（标准库 http.server，~250 行）
  ├─ 静态文件
  ├─ /api/search   DuckDuckGo 优先 + Jina 兜底
  └─ /api/quote    yfinance 行情/估值（服务端 round 2 位）
```

**关键取舍**：调研过开源 DeepSeek harness（DeepSeek-Agent 是 Python 服务端 app；LangGraph.js / Vercel AI SDK 都要 npm 构建/后端），没有能塞进「单文件零构建」的。而 DeepSeek 工具调用是标准协议（`tools`→`tool_calls`→`role:tool`），~60 行即可，遂手写，不引框架。

---

## 二、核心实现

### 1. 选中即问（浮层批注 → 挂对话）
- 文档：编辑器 `mousedown` 进拖选态、`mouseup` 才弹浮层（见 bug ④）；预览(docx)用原生 selection。
- 浮层写批注 → 回车**挂到主对话框上方的引用堆**（不发送），可堆多条，最后统一 batch 发出；引用堆每个对话 tab 独立。

### 2. AI 工具 harness（本日重点，三次迭代）
- **v0**：二元 `decideSearch` —— 单独一个 LLM 调用判断「要不要搜」。**错的抽象**：它只看到光秃秃的问题、看不到打开的文件，理解不了「这家公司」=当前文档。
- **v1**：function-calling 工具循环 —— 模型带**完整上下文**(文件/选区/对话) → 决定调 `web_search`/`get_quote` → 执行 → 多轮。规划走 Flash、作答走用户选的模型。
- **v2（最终）**：发现 **V4 Pro 同时支持 tools + reasoning + streaming**，合并成**单模型流式 ReAct**：一条流里边流式吐 `reasoning_content`(灰色 COT) 边决定调工具 → 执行(`role:tool` 回灌) → 继续思考 → 作答。COT 在调工具**之前**就上屏。
- 流式 tool_calls 解析：`delta.tool_calls` 按 `index` 累积 id/name，`arguments` 跨 delta 字符串拼接。

### 3. AI 直接改文件（uniwork-ops + 逐条批阅）
- 模型在回答末尾附隐藏 JSON：`{target:doc/sheet, ops:[…]}`，前端解析后应用：
  - 表格 `setCell` → Luckysheet 真实算 + 黄高亮 + 撤销/接受。
  - 文档 `replace/append` → TipTap **绿增红删**建议标记。
- **逐条批阅**：每个 op 一个 `sid`(建议组 id) 写进 mark 属性；ProseMirror 装饰在每组末尾注入行内 `✓/✗`；`recountSugg()` 数剩余 sid，批完→0→顶部「全部」条消失。
- append 走 `marked.parse` → `insertContentAt`，**沿用文档已有版式**(标题/bullet/缩进)，不再平铺纯文本。

### 4. 数据正确性
- 价格类：yfinance → /api/quote **服务端 round 2 位** → 模型逐字搬运 → 卡片三处对齐。验证过：/api/quote 与独立 Yahoo 源逐一致；模型答案里的数字 = 工具返回值(无篡改)。
- system prompt 注入**当前真实日期**，修 DeepSeek 时间感知。

### 5. 持久化（IndexedDB）
- `serFile/serSession` 只产可结构化克隆的纯对象（docx ArrayBuffer / xlsx Blob / 表格 lsData 快照都能直接存）。
- 防抖自动保存 + 启动 `hydrate()` 还原；`?reset` 清库。

---

## 三、主要 bug 与修复

| # | Bug | 根因 | 修复 |
|---|---|---|---|
| ① | docx 字体 100pt 巨大 | 样例文件自带 `w:sz=200` | 换正常文件；预览改 docx-preview 高保真 |
| ② | Luckysheet 撑出 5,000,000px | 内部 canvas 溢出 | 三层 wrapper `overflow:hidden` |
| ③ | Cmd+D 填充出 value 不出公式 | `getCellValue(type:f)` 返回 HTML 包装串 | 3 通道取公式 + 剥 HTML + `$` 绝对引用不平移 |
| ④ | **md 只能选一个字** | `onSelectionUpdate` 拖选途中弹浮层、autofocus 抢走 contenteditable 焦点→选区塌缩 | `mousedown` 进拖选态先不弹，`mouseup` 才弹+聚焦；键盘选区不抢焦点 |
| ⑤ | AI 改 docx「看不到修改」 | 预览态没切编辑、suppressDirty 竞态 | 改动前自动切编辑态；`persistDocGroundTruth()` 作唯一同步出口 |
| ⑥ | 模型谎称「我不能联网」 | sys prompt 只在「有搜索结果时」才提联网，没结果时模型自作主张免责 | 基础 prompt 写死「你具备按需联网能力，严禁声称无法联网」 |
| ⑦ | 搜索慢/有时 0 条 | Jina 在本机 SSL 必失败、白等 2-3s | 改 DuckDuckGo 优先、Jina 兜底；空结果注入「宁缺毋假」提示 |
| ⑧ | decideSearch 理解不了意图 | 二元预判器看不到文件上下文 | 重构成带完整上下文的工具 harness（见上 §2.2） |
| ⑨ | 数字带一长串浮点 `208.190002…` | yfinance 原始 float 漏出 + 模型自行截位 | 服务端统一 `round(2)`，模型只搬运 |
| ⑩ | 流式时跳到底部 source | sources 中途赋值 + 自动滚动 | 流式 ReAct 里 sources 在答案后才赋值 + `v-if !streaming` 双保险 |
| ⑪ | akshare 装不上 | Python 3.9 + 老 pip resolver 依赖冲突 + LibreSSL EOF | 弃用 get_cn_macro，留休眠扩展位 |

### 踩过的工程坑
- **逐条批阅的 prosemirror 实例**：行内 ✓/✗ 用 ProseMirror 装饰，`Plugin/Decoration` 必须从 `@tiptap/pm/*` 取（与编辑器同实例），否则重复 prosemirror 会让编辑器崩。
- **流式作答 vs 工具轮内容**：工具轮模型会吐「好的我查一下」引导语，流完若有 tool_calls 就把 `aiMsg.content` 清掉（思考已在灰色 reasoning 里），只留最终轮内容作答案。
- **持久化死循环**：序列化前台表格时实时读 `getAllSheets()` 但**不写回 reactive**，否则 deep-watch 自触发。

---

## 四、模型说明

DeepSeek API 已升 V4：`deepseek-v4-pro`（默认，带思考）/ `deepseek-v4-flash`。两档都支持 tools + reasoning + streaming（旧 `deepseek-reasoner` 不支持 tools，V4 起统一）。
