"""把 app/ui 下被加载的样式表中所有小于 14px 的字号统一提到 14px。

依据：导师"除标题外文本字体最多五号（约 14px）且必须统一"；
HANDOFF/10 裁决 5 —— 完成标准分两阶段：
    阶段一 可见文本 below14 == 0
    阶段二 除标题外全部收敛到同一个值（建议 14px），>14px 的元素也要收敛
把 <14px 一律提到 14px，对受影响的元素而言同时满足了两个阶段。

同时处理：
  · font-size:12px 这类常规声明
  · font:9px Consolas 这类简写（只改其中的字号，其余保留）
限定只认 4~13.99px 之间，以免误伤 max-width:6101px 之类的非字号数值。

用法：runtime/python/python.exe app/tests/_bump_fonts.py [--apply]
      不加 --apply 只预览改动，不写盘。
"""
import re
import sys
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "ui"
TARGET = 14
LOADED = ["style.css", "theme-v2.css", "alert-center.css", "selfcheck.css"]

decl_re = re.compile(r"(font-size:\s*)([0-9]+(?:\.[0-9]+)?)px", re.I)
short_re = re.compile(r"(\bfont:\s*)([0-9]+(?:\.[0-9]+)?)px", re.I)


def _make_sub(counter):
    def _repl(m):
        val = float(m.group(2))
        if 4.0 <= val < TARGET:
            counter[0] += 1
            return f"{m.group(1)}{TARGET}px"
        return m.group(0)
    return _repl


apply_changes = "--apply" in sys.argv
grand = 0
for name in LOADED:
    p = UI / name
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    counter = [0]
    repl = _make_sub(counter)
    new_text = short_re.sub(repl, decl_re.sub(repl, text))
    grand += counter[0]
    if counter[0]:
        print(f"{name}: {counter[0]} 处")
        if apply_changes:
            p.write_text(new_text, encoding="utf-8")
    elif apply_changes:
        pass

print(f"\n合计 {grand} 处" + ("（已写盘）" if apply_changes else "（预览，未写盘；加 --apply 生效）"))
