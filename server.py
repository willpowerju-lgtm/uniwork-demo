#!/usr/bin/env python3
"""Uniwork demo 本地服务器：静态文件 + /api/search 联网搜索代理（服务端跑，规避浏览器 CORS）。
搜索源优先 Jina（s.jina.ai），失败回退 DuckDuckGo HTML。"""
import json, os, re, socket, sys, urllib.parse, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.chdir(os.path.dirname(os.path.abspath(__file__)))   # 静态根=脚本所在目录，与启动位置无关
socket.setdefaulttimeout(25)   # 防外部请求挂死拖垮整个服务

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4188
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


def _get(url, headers=None, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def search_jina(q, n=5):
    """Jina 搜索：返回 [{title,url,content}]"""
    url = "https://s.jina.ai/?q=" + urllib.parse.quote(q)
    raw = _get(url, headers={"Accept": "application/json", "X-Respond-With": "no-content"})
    data = json.loads(raw)
    items = data.get("data") or data.get("results") or []
    out = []
    for it in items[:n]:
        out.append({
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "content": (it.get("description") or it.get("content") or "")[:500],
        })
    return out


def _strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def _unwrap(href):
    mm = re.search(r"uddg=([^&]+)", href)
    return urllib.parse.unquote(mm.group(1)) if mm else href


def search_ddg(q, n=5):
    """DuckDuckGo HTML 回退：findall 配对 标题/链接/摘要"""
    html = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q))
    links = re.findall(r'class="result__a"[^>]*?href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    out = []
    for i, (href, title) in enumerate(links[:n]):
        out.append({
            "title": _strip(title),
            "url": _unwrap(href),
            "content": _strip(snips[i]) [:500] if i < len(snips) else "",
        })
    return out


# ===== 数据工具：yfinance 行情/估值 · akshare 中国宏观（懒加载，缺库不影响服务启动）=====
import time
_CACHE = {}   # key -> (ts, data)；进程内 60s 简单缓存，省重复抓取


def _cached(key, ttl, producer):
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    data = producer()
    _CACHE[key] = (time.time(), data)
    return data


def _fi(fi, *keys):
    """FastInfo 同时支持 dict 键和 snake_case 属性，逐个兜底取值"""
    for k in keys:
        try:
            v = fi[k]
            if v is not None:
                return v
        except Exception:
            pass
        try:
            v = getattr(fi, k)
            if v is not None:
                return v
        except Exception:
            pass
    return None


def fetch_quote(symbol):
    """yfinance：全球股票现价/涨跌/估值。symbol 如 AAPL / 0700.HK / 600519.SS / 000001.SZ"""
    import yfinance as yf
    t = yf.Ticker(symbol)
    fi = t.fast_info
    price = _fi(fi, "lastPrice", "last_price")
    prev = _fi(fi, "previousClose", "previous_close", "regularMarketPreviousClose")
    cur = _fi(fi, "currency")
    mcap = _fi(fi, "marketCap", "market_cap")
    hi52 = _fi(fi, "yearHigh", "year_high")
    lo52 = _fi(fi, "yearLow", "year_low")
    name = None
    pe = None
    try:                                  # .info 更全但慢/偶缺，包起来
        info = t.info or {}
        name = info.get("shortName") or info.get("longName")
        pe = info.get("trailingPE")
        mcap = mcap or info.get("marketCap")
        cur = cur or info.get("currency")
    except Exception:
        pass
    if price is None:
        return {"symbol": symbol, "error": "未取到行情（symbol 可能有误，A股用 .SS/.SZ，港股用 .HK）"}
    chg = (price - prev) if (price is not None and prev) else None
    chgpct = (chg / prev * 100) if (chg is not None and prev) else None
    r2 = lambda x: round(x, 2) if isinstance(x, (int, float)) else x   # 价格类统一保留 2 位（Python 做，不交给 LLM）
    return {"symbol": symbol, "name": name, "price": r2(price), "currency": cur,
            "change": r2(chg), "changePct": r2(chgpct), "prevClose": r2(prev),
            "pe": r2(pe), "marketCap": mcap, "week52High": r2(hi52), "week52Low": r2(lo52)}


# indicator -> (akshare 函数名, 口径说明)；函数名落地时按本机 akshare 版本核实
MACRO_FN = {
    "cpi": ("macro_china_cpi_monthly", "CPI 当月同比 (%)"),
    "ppi": ("macro_china_ppi_yearly", "PPI 当月同比 (%)"),
    "pmi": ("macro_china_pmi_yearly", "制造业 PMI"),
    "gdp": ("macro_china_gdp_yearly", "GDP 当季同比 (%)"),
    "m2":  ("macro_china_m2_yearly", "M2 同比 (%)"),
}


def fetch_cn_macro(indicator):
    """akshare：中国宏观（yfinance 没有的中国数据）。返回最近若干期数值。"""
    key = (indicator or "").lower().strip()
    if key not in MACRO_FN:
        return {"error": "未知指标", "supported": list(MACRO_FN)}
    import akshare as ak
    fn_name, desc = MACRO_FN[key]
    fn = getattr(ak, fn_name, None)
    if fn is None:
        return {"error": "本机 akshare 无 %s" % fn_name, "supported": list(MACRO_FN)}
    df = fn()
    try:
        df = df.reset_index()
    except Exception:
        pass
    rows = []
    try:
        tail = df.tail(8)
        cols = [str(c) for c in tail.columns]
        for _, r in tail.iterrows():
            rows.append({c: (None if str(r[oc]) == "nan" else str(r[oc])) for c, oc in zip(cols, tail.columns)})
    except Exception as e:
        return {"error": "解析失败: %s" % str(e)[:80], "indicator": key}
    return {"indicator": key, "desc": desc, "source": "akshare:" + fn_name, "data": rows}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/search"):
            return self.handle_search()
        if self.path.startswith("/api/quote"):
            return self.handle_quote()
        if self.path.startswith("/api/cn_macro"):
            return self.handle_cn_macro()
        return super().do_GET()

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _arg(self, name):
        qs = urllib.parse.urlparse(self.path).query
        return (urllib.parse.parse_qs(qs).get(name) or [""])[0].strip()

    def handle_quote(self):
        sym = self._arg("symbol")
        if not sym:
            return self._json({"error": "缺 symbol"})
        try:
            data = _cached("q:" + sym, 60, lambda: fetch_quote(sym))
        except Exception as e:
            data = {"symbol": sym, "error": str(e)[:160]}
        return self._json(data)

    def handle_cn_macro(self):
        ind = self._arg("indicator")
        try:
            data = _cached("m:" + ind, 600, lambda: fetch_cn_macro(ind))
        except Exception as e:
            data = {"indicator": ind, "error": str(e)[:160]}
        return self._json(data)

    def handle_search(self):
        q = self._arg("q")
        result = {"query": q, "results": [], "source": None}
        if q:
            # DuckDuckGo 优先（稳定、~4-5s）；Jina 作兜底（部分网络/SSL 环境对 s.jina.ai 握手失败）
            for name, fn in (("duckduckgo", search_ddg), ("jina", search_jina)):
                try:
                    r = fn(q)
                    if r:
                        result["results"], result["source"] = r, name
                        break
                except Exception as e:
                    result["error_%s" % name] = str(e)[:160]
        return self._json(result)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print("Uniwork server on http://localhost:%d  (static + /api/search + /api/quote + /api/cn_macro)" % PORT)
    srv = ThreadingHTTPServer(("", PORT), Handler)
    srv.daemon_threads = True
    srv.serve_forever()
