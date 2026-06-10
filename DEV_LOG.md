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
| ⑫ | **同一对话上下文断裂、模型自称"看不到之前对话"、像是 md 注入丢了** | v2 流式 ReAct 重构后 `runHarness` 的 `msgs` 只塞 `[system, 当前user]`，从不带 `sess.messages` 历史 → 每轮都是空白起点，连带上一轮注入的文档内容也"消失" | `send()` 在 push 新消息前把 `sess.messages` 映射成 API 历史（user 经 `fmtUserTurn` 复原引用+批注，ai→assistant，空内容跳过）传入 `runHarness`，`msgs=[system, ...history, 当前user]`；兜底 streamDeepSeek 同样带 history。E2E：第2轮请求 roles 由 `[system,user]` → `[system,user,assistant,user]`，上一轮暗号可见 |
| ⑬ | **文件上下文"持久挂载"不完整**：通用会话一切预览就丢上下文；后台绑定的表格无单元格数据、docx 取原始非编辑稿 | 通用(未绑定)会话 `ctxFile=boundFileOf‖active.value` 永远跟随前台预览；后台 sheet 只回一句提示语；后台 doc 注入 `f.html` 而非 `editedHtml` | (1) 通用会话**首问自动钉住当前文件**（`!sess.bound&&active.value→sess.bound=active.value.id`），tab 由"通用"变"上下文：X"，之后切预览不漂；(2) 后台绑定表格从 `f.lsData` 快照注入单元格（新 `snapSheetObj`/`sheetSnapshotFrom`，`data` 优先 `celldata` 兜底）；(3) 后台绑定 docx 读 `editedHtml‖html`——**防御性兜底，非真修复**：`onUpdate`/`persistDocGroundTruth` 已把 `f.html` 与 `editedHtml` 实时同源写入，故与旧 `f.html` 取值等价，行为不变（保留以防未来出现只写 editedHtml 的路径）。E2E：①②实测通过（绑定文件跨轮钉死、后台表格注入真实 `A1=科目∣B2=32.99…`、通用会话首问后 tab"通用"→"上下文：X"且切预览不漂）；③ 读码确认 + 后台 docx **内容注入**已验证（注入读 model 的 `getHTML()`：DOM-only 改动不串入，证明读的是文档模型而非脏 DOM）。脚本化"真编辑"无法从外部驱动 ProseMirror 事务，故未单独 E2E |

### 踩过的工程坑
- **逐条批阅的 prosemirror 实例**：行内 ✓/✗ 用 ProseMirror 装饰，`Plugin/Decoration` 必须从 `@tiptap/pm/*` 取（与编辑器同实例），否则重复 prosemirror 会让编辑器崩。
- **流式作答 vs 工具轮内容**：工具轮模型会吐「好的我查一下」引导语，流完若有 tool_calls 就把 `aiMsg.content` 清掉（思考已在灰色 reasoning 里），只留最终轮内容作答案。
- **持久化死循环**：序列化前台表格时实时读 `getAllSheets()` 但**不写回 reactive**，否则 deep-watch 自触发。

---

## 四、模型说明

DeepSeek API 已升 V4：`deepseek-v4-pro`（默认，带思考）/ `deepseek-v4-flash`。两档都支持 tools + reasoning + streaming（旧 `deepseek-reasoner` 不支持 tools，V4 起统一）。

---

## 五、增补 · 2026-06-11（Word 单视图 + PDF 预览）

### 1. Word 改为单一所见即所得可编辑视图
- **动机**：旧 docx 是「docx-preview 高保真只读」+「TipTap 编辑」两态切换；用户编辑后切回预览，预览渲染 `editedHtml`（非 docx-preview），格式与高保真态不一致 → 观感「格式炸裂」，且来回切换烦。
- **做法**：删除 `docx-preview` CDN、`renderDocxPreview`/`toggleDocxView`/`docxRenderedId`/`f.view` 全链路；docx 打开即 TipTap 可编辑纸张视图。`persistDocGroundTruth` 简化为只写 `f.html`/`f.editedHtml`+`saveFilesSoon`。新增 TipTap `extension-image(allowBase64)` 让 mammoth 内嵌图保真（否则 StarterKit 丢 `<img>`）。导出仍 html-docx-js。
- **收益**：无切换、无格式炸裂；AI 改写/逐条批阅/手动编辑全在同一视图直接落。

### 2. PDF 预览模块（pdf.js）
- **栈**：pdf.js 3.11.174 UMD（`window.pdfjsLib`，worker 惰性指 CDN）。`renderPdf` 每页画 canvas（devicePixelRatio 高清，宽度自适应 0.6~2 限幅）+ 叠 `.textLayer` 文字层（可选中→ document `mouseup` 监听 scope `#pdf-host` → 浮层「加入对话」）；全文存 `f.pdfText`(≤20k) 进 AI 上下文。`#pdf-host` 单宿主，`pdfRenderedId` 同文件复用、`pdfRenderToken` 防切走竞态。上传/持久化/导出（原样下载）/`@`引用全打通。样例 `sample_Autel_InitiatingCoverage.pdf` 由 `make_sample_pdf.py` 手搓。

### 主要 bug
| # | 现象 | 根因 | 修法 |
|---|------|------|------|
| ⑭ | **PDF `page.render()` 永不 resolve**：canvas 卡空白、`pdfLoading` 不灭，但 `getTextContent`/文字层正常 | pdf.js `InternalRenderTask` 用 `requestAnimationFrame` 分块绘制 canvas；浏览器在 `document.hidden`（后台/无头 Preview，`visibilityState=hidden`）时暂停 rAF → 绘制链断。worker 调用（getTextContent）不走 rAF 故不受影响 | 渲染期间 `rafShimOn()` 把 `window.requestAnimationFrame` 临时垫成 `setTimeout(cb,0)`、`finally` `rafShimOff()` 还原（refcount 兼容并发）。可见标签页里 setTimeout 版 rAF 对一次性文档渲染无可感副作用。**Claude Preview 标签页恒为 hidden，正是靠此才能 E2E 验** |
| ⑮ | 新增样例 PDF 不出现 | `hydrate()` 成功（老 IndexedDB 有数据）会跳过 `preloadSamples()` | 设计如此；`?reset` 清库后重新 seed 即见。已有用户数据则直接拖 PDF 上传验证 |

### 验证（E2E，Claude Preview 4189）
Word：docx 打开即可编辑（`.ProseMirror[contenteditable]`）、无切换钮、4 标题+1 表格保真、插入文字格式不炸、autosave。PDF：2 页 canvas + 62 文字 span、选中弹「挂到对话」浮层(340×74)、`pdfText` 进上下文、切走再回复用、与 docx/xlsx 互切无回归、console 零报错。

### 增补 bug（2026-06-11 续）
| # | 现象 | 根因 | 修法 |
|---|------|------|------|
| ⑯ | **批注字数一多浮层自动跳掉、批注静默丢失** | 收起浮层用的 `window.addEventListener('scroll',()=>bubble.show=false, true)` 是**捕获阶段**，会捕获到批注 `<input>` 文字溢出框宽时的**内部横向自滚** scroll 事件 → 误判为页面滚动 → 浮层被收起，批注没挂上也无提示 | scroll 回调加 `if(e.target.closest('.bubble-pop')) return`（框内滚动忽略）；并把批注 input 换成自增高 `<textarea>`（`autosizeBubble`，Enter 挂载 / Shift+Enter 换行），长批注换行可见、根本不再横滚。E2E：100 字批注触发 input scroll 后浮层仍在、Enter 后引用+批注完整挂入对话 |

### 3. WIKI / Vault 文件夹树 + Obsidian 式双链（2026-06-11）
- **结构**：侧栏平铺 → 可折叠树。顶层 📚 WIKI（每公司一页 wiki md）/ 🗄️ Vault（每公司文件夹 → 研报 / 季报年报 / Model / News / Raw）。
- **数据模型**：文件加 `folder` 路径字段；`folders`（路径数组，空文件夹也显示）+ `expandedFolders`（展开状态）+ `treeRows` computed（扁平化、尊重展开）。三者全持久化；老用户 hydrate 无 `folders` 时按 `SEED_FOLDER_OF` 迁移、uploads 归根。`openFile` 自动 `expandAncestors` 展开上级。
- **双链**：`[[笔记名]]`（含 `|别名`）→ `WikiLink`（ProseMirror inline decoration）在编辑器里实时着色可点（蓝=解析 / 红=未解析）；`editor.dom` **capture 阶段 mousedown** 抢在 PM 放光标前 → `navigateWikilink`：解析 `openFile`、未解析 `createNoteFromLink`（建空笔记，Obsidian 行为）。`resolveNote` 按去扩展名的笔记名跨 WIKI+Vault 匹配。
- **反向链接**：`backlinks` computed 扫所有 doc 的 html 文本里 `[[本笔记名]]`，带上下文片段，面板挂在笔记底部（`.ed-scroll` 改 column 让卡片叠在纸张下）。
- **E2E（Claude Preview 4189）**：树 17 行结构正确（含 async 装载的 pdf/xlsx/docx 各归其位、空文件夹显示）；4 个 `[[ ]]` 全解析；点 `[[道通科技_2024Q3点评]]` 跳转成功；该笔记反向链接 = 3（wiki + 研报 + news，带片段）；打字插入 `[[测试新笔记]]` 显红、点击建笔记并入树；普通 reload 后 14 文件夹 + 双链全还原；console 零报错。
