#!/usr/bin/env python3
# 生成一个用于 Uniwork PDF 预览模块演示/测试的研报样例 PDF（标准 Helvetica 字体，无需嵌入）。
# 纯标准库手搓 PDF，xref 偏移按字节实时计算，保证 pdf.js 可渲染 + 文字层可选中。
import sys

PAGE_W, PAGE_H = 612, 792
MARGIN = 60

def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def content_for(lines):
    """lines: list of (x, y_from_top, font_key, size, text). font_key in {'F1','F2'}."""
    out = []
    # 顶部一条品牌色细线
    out.append("0.20 0.44 1.0 rg")
    out.append(f"{MARGIN} {PAGE_H-78} {PAGE_W-2*MARGIN} 2 re f")
    out.append("0 0 0 rg")
    for (x, ytop, fk, size, text) in lines:
        y = PAGE_H - ytop
        out.append("BT")
        out.append(f"/{fk} {size} Tf")
        out.append(f"{x} {y:.1f} Td")
        out.append(f"({esc(text)}) Tj")
        out.append("ET")
    return "\n".join(out).encode("latin-1")

page1 = [
    (MARGIN, 56, "F2", 20, "Autel Robotics (688208.SH) - Initiating Coverage"),
    (MARGIN, 74, "F1", 10.5, "Orchid Asia  |  Buy-Side Research  |  Sample PDF rendered in Uniwork preview"),
    (MARGIN, 112, "F2", 13, "Investment Thesis"),
    (MARGIN, 134, "F1", 10.5, "We initiate coverage of Autel Robotics with a BUY rating and a 12-month target"),
    (MARGIN, 150, "F1", 10.5, "price of RMB 78. Autel is a leading designer of professional drones and intelligent"),
    (MARGIN, 166, "F1", 10.5, "diagnostics, with an expanding footprint in industrial inspection and public safety."),
    (MARGIN, 182, "F1", 10.5, "We see three drivers: (1) share gains in enterprise UAV as Western buyers diversify"),
    (MARGIN, 198, "F1", 10.5, "away from incumbents; (2) attach-rate upside from payload and software subscriptions;"),
    (MARGIN, 214, "F1", 10.5, "(3) operating leverage as the new Shenzhen line ramps through 2026."),
    (MARGIN, 250, "F2", 13, "Key Financials (RMB mn)"),
    (MARGIN, 274, "F2", 10.5, "Metric"),
    (MARGIN+170, 274, "F2", 10.5, "FY24"),
    (MARGIN+260, 274, "F2", 10.5, "FY25E"),
    (MARGIN+350, 274, "F2", 10.5, "FY26E"),
    (MARGIN, 294, "F1", 10.5, "Revenue"),
    (MARGIN+170, 294, "F1", 10.5, "4,210"),
    (MARGIN+260, 294, "F1", 10.5, "5,480"),
    (MARGIN+350, 294, "F1", 10.5, "7,020"),
    (MARGIN, 312, "F1", 10.5, "Gross margin"),
    (MARGIN+170, 312, "F1", 10.5, "52.1%"),
    (MARGIN+260, 312, "F1", 10.5, "53.4%"),
    (MARGIN+350, 312, "F1", 10.5, "54.0%"),
    (MARGIN, 330, "F1", 10.5, "Net income"),
    (MARGIN+170, 330, "F1", 10.5, "402"),
    (MARGIN+260, 330, "F1", 10.5, "631"),
    (MARGIN+350, 330, "F1", 10.5, "928"),
    (MARGIN, 348, "F1", 10.5, "Diluted EPS"),
    (MARGIN+170, 348, "F1", 10.5, "0.95"),
    (MARGIN+260, 348, "F1", 10.5, "1.49"),
    (MARGIN+350, 348, "F1", 10.5, "2.19"),
    (MARGIN, 392, "F1", 9, "Page 1 of 2  -  For demonstration only. Not investment advice."),
]

page2 = [
    (MARGIN, 56, "F2", 16, "Risks & Valuation"),
    (MARGIN, 96, "F2", 13, "Key Risks"),
    (MARGIN, 118, "F1", 10.5, "- Export-control and tariff overhang on dual-use UAV components."),
    (MARGIN, 134, "F1", 10.5, "- Competitive pricing from incumbents could compress attach-rate economics."),
    (MARGIN, 150, "F1", 10.5, "- FX translation: a meaningful share of revenue is USD/EUR denominated."),
    (MARGIN, 166, "F1", 10.5, "- Execution risk on the Shenzhen capacity ramp into 2026."),
    (MARGIN, 204, "F2", 13, "Valuation"),
    (MARGIN, 226, "F1", 10.5, "Our RMB 78 target is set on 35x FY26E EPS of RMB 2.19, a premium we justify by"),
    (MARGIN, 242, "F1", 10.5, "above-peer revenue CAGR (28%) and a widening software mix. A bear case of RMB 52"),
    (MARGIN, 258, "F1", 10.5, "assumes margin reversion to 50% and a 25x multiple; a bull case of RMB 104 assumes"),
    (MARGIN, 274, "F1", 10.5, "subscription attach reaching 30% of installed base by FY27."),
    (MARGIN, 312, "F2", 13, "Catalysts (next 6 months)"),
    (MARGIN, 334, "F1", 10.5, "1. FY25 results and FY26 capacity guidance."),
    (MARGIN, 350, "F1", 10.5, "2. New enterprise payload launch at the spring trade show."),
    (MARGIN, 366, "F1", 10.5, "3. Potential inclusion in the STAR50 index review."),
    (MARGIN, 410, "F1", 9, "Page 2 of 2  -  Orchid Asia  -  Sample document for Uniwork PDF preview."),
]

# 组装对象
objs = {}
objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
objs[2] = b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>"
res = b"<< /Font << /F1 7 0 R /F2 8 0 R >> >>"
objs[3] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources " + res + b" /Contents 5 0 R >>"
objs[4] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources " + res + b" /Contents 6 0 R >>"
c1 = content_for(page1); c2 = content_for(page2)
objs[5] = b"<< /Length " + str(len(c1)).encode() + b" >>\nstream\n" + c1 + b"\nendstream"
objs[6] = b"<< /Length " + str(len(c2)).encode() + b" >>\nstream\n" + c2 + b"\nendstream"
objs[7] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
objs[8] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"

out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
offsets = {}
for n in range(1, 9):
    offsets[n] = len(out)
    out += str(n).encode() + b" 0 obj\n" + objs[n] + b"\nendobj\n"
xref_pos = len(out)
out += b"xref\n0 9\n0000000000 65535 f \n"
for n in range(1, 9):
    out += ("%010d 00000 n \n" % offsets[n]).encode()
out += b"trailer\n<< /Size 9 /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"

with open(sys.argv[1], "wb") as f:
    f.write(out)
print("wrote", sys.argv[1], len(out), "bytes")
