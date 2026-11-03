"""列出被加载的 CSS 中所有小于 14px 的 font-size 声明（含 文件:行 与原始声明）。

为什么需要：导师要求"除标题外字体最多五号约 14px 且必须统一"，
即 HANDOFF/10 裁决 5 定义的两阶段标准（阶段一 below14==0，阶段二收敛到同一值）。
相关声明散落在多个 css 里，靠人眼逐个找不可靠，也不好复现。

用法：runtime/python/python.exe app/tests/_audit_fonts.py [下限px，缺省 14]
"""
import re
import sys
from collections import Counter
from pathlib import Path

# 本脚本放在 app/tests/，而要审计的样式表在 app/ui/
UI = Path(__file__).resolve().parent.parent / "ui"

# index.html 里真正 link 进来的样式表（其余 css 未被引用，改它们对页面没有效果）
LOADED = ["style.css", "theme-v2.css", "alert-center.css", "selfcheck.css"]

THRESHOLD = float(sys.argv[1]) if len(sys.argv) > 1 else 14.0

decl_re = re.compile(r"font-size:[^;}]*", re.I)
num_re = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
# 同时处理 font: 12px/1.4 这类简写
short_re = re.compile(r"\bfont:\s*(?:[0-9]+\s+)?([0-9.]+)px", re.I)

rows = []
for name in LOADED:
    p = UI / name
    if not p.exists():
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for m in decl_re.finditer(line):
            nm = num_re.search(m.group(0))
            if nm and float(nm.group(1)) < THRESHOLD:
                rows.append((name, i, m.group(0).strip(), "font-size"))
        for m in short_re.finditer(line):
            if float(m.group(1)) < THRESHOLD:
                rows.append((name, i, line.strip()[:70], "font 简写"))

print(f"被加载的 CSS 共 {len(LOADED)} 个；小于 {THRESHOLD:g}px 的声明 {len(rows)} 条")
print(f"{'文件':<18}{'行':>5}  {'原始声明':<24}{'类型'}")
print("-" * 76)
for name, no, decl, kind in rows:
    print(f"{name:<18}{no:>5}  {decl:<24}{kind}")

print("\n按数值分布:", dict(sorted(Counter(float(num_re.search(r[2]).group(1)) for r in rows).items())))
print("按文件分布:", dict(Counter(r[0] for r in rows)))
