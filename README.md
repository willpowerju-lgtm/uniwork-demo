# Uniwork · 选中即问的 AI 投研工作台（单文件 Demo）

把 **Word / Excel / Markdown** 直接在浏览器里打开、编辑，配一个**会思考、会联网、会查行情、能直接改你文件**的 AI 助手。

> 单文件 `index.html`（Vue 3 + 全 CDN，零构建）+ 一个 ~200 行的 Python 后端代理。逆向自 AlphaPai/PaiWork 的「选中即问」交互，接 DeepSeek。

---

## ✨ 它能做什么

- **四类文件**：md / docx → **所见即所得，打开即可直接编辑**（TipTap，无预览/编辑切换）；xlsx / csv → 真·Excel（Luckysheet，公式、Cmd+D 填充）；**pdf → 高清预览（pdf.js），文字可选中**。
- **选中即问**：在文档里划选文字、表格里框选单元格、或 **PDF 上选中文字** → 浮层写批注 → 回车挂到对话（可挂多条，一起发）。
- **先思考再行动**：默认 **DeepSeek V4 Pro**，**灰色流式展示思考过程（COT）**，想清楚了才决定要不要调工具 —— 一条**流式 ReAct** 循环。
- **按需用工具**（function calling）：
  - `web_search` —— 要最新消息/新闻/查证就联网搜（答案带来源 `[n]`）；
  - `get_quote` —— 要股价/估值就查行情（yfinance：美股 `AAPL` / 港股 `0700.HK` / A股 `600519.SS`·`000001.SZ`，含 PE、市值）。
  - 纯文档分析 / 概念题 / 润色 **不乱调工具**。
- **AI 直接改文件**：让它"补充 / 修改 / 计算"，改动以**绿增红删**呈现，可**逐条 ✓/✗ 批阅**或全部接受/拒绝；新增内容沿用你文档的版式（标题/bullet/缩进）。
- **上下文**：当前文件自动注入；`@` 引用其它文件；选中→「加入对话」引用片段。
- **其它**：多对话 tab（≤3）并行、`/` 命令、`Esc` 中断、刷新不丢（本地 IndexedDB 持久化）。

## 🚀 快速开始

```bash
# 1) 装后端依赖（行情工具用，联网搜索是纯标准库）
python3 -m pip install -r requirements.txt

# 2) 起服务（静态 + /api/search 联网代理 + /api/quote 行情代理）
python3 server.py 4188

# 3) 浏览器打开 http://localhost:4188  （硬刷新 Cmd/Ctrl+Shift+R）
```

**配置 DeepSeek Key**（二选一）：
- 点页面右下角 🔑 **「设置 Key」** 粘贴 —— 存在你浏览器 localStorage，不上传、不进仓库；**或**
- `cp config.local.js.example config.local.js`，把 `sk-…` 填进去（该文件已 gitignore）。

没 Key 也能开，但 AI 回复走 Mock 占位。Key 在 https://platform.deepseek.com/ 创建。

## 🧠 设计理念

- **先思考再调工具**：模型先用 COT 想清你的真实意图（结合打开的文件/选区/对话），再决定调哪个工具、查什么 —— 不是无脑的二元预判。
- **数值原子性**：价格/估值等精确数字一律来自工具接口，**模型只逐字搬运、不编造不换算**，并标来源；服务端统一 `round(2)`。
- **宁缺毋假**：工具没取到就如实说"取不到、请自行核实"，绝不拿训练知识冒充实时数据。

## 🏗 架构一览

```
浏览器（单文件 index.html，Vue3 + CDN）
  ├─ 文档  TipTap(+image) / mammoth / html-docx-js / turndown   ·   PDF  pdf.js(canvas+文字层)
  ├─ 表格  Luckysheet / LuckyExcel / SheetJS
  ├─ AI    DeepSeek V4（OpenAI 兼容）：流式 ReAct（reasoning_content + 原生 tools）
  └─ 存储  IndexedDB（文件二进制 / 会话 / UI 状态，刷新不丢）
        │  浏览器直连 api.deepseek.com（CORS 放行）
        ▼
Python server.py（标准库 http.server）
  ├─ 静态文件
  ├─ /api/search   DuckDuckGo（Jina 兜底）联网搜索代理（规避 CORS）
  └─ /api/quote    yfinance 行情/估值代理
```

工具 harness 是手写的标准 function-calling 循环（DeepSeek `tools` → `tool_calls` → `role:tool`），没引框架 —— 协议本身就一页纸，对单文件零构建更合适。详见 [`DEV_LOG.md`](DEV_LOG.md)。

## 🔐 安全

- **API Key 绝不进仓库**：`config.local.js` 已 gitignore；分享出去的版本靠 🔑 按钮各自粘自己的 Key（存各自浏览器）。
- 这是个**前端直连 Key 的 Demo**，适合本地/可信分享；真要公网部署，应改成后端代理持 Key、前端不碰。

## 📄 说明

研究/教学用 Demo，AI 输出仅供参考，不构成投资建议。
