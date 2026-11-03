# -*- coding: utf-8 -*-
"""打包"给另一个 AI 的接手知识包"。

为什么要这个脚本
----------------
只把某几个文件丢给新会话的 AI，很容易漏东西，尤其是：本项目的工作记忆放在
C:\\Users\\...\\WorkBuddy\\...\\.workbuddy\\memory 下，**不在项目目录里**。
如果只拷项目目录，那些记录就会全部丢失。本脚本把接手所需的全部材料
（含项目外的工作记忆快照）汇聚到一个目录，并额外产出一个可整个粘贴给
新 AI 的单文件总纲，确保不遗漏。

产物
----
  AI_PACK/
    00_先读_给接手AI的总纲.txt     ← 单文件版，可直接整个喂给新的 AI
    HANDOFF/*                      00–07 全部交接文档
    context_snapshot.json          机器可读的现状快照
    AI_START_HERE.txt              项目根目录的接手入口
    memory_snapshot/               项目外 .workbuddy/memory 的快照（长期事实 + 近期日志）
    docs_contracts/                关键契约（接口/交付/链路等）
    文件清单.txt                    本次打包了哪些文件、各自多大

用法
----
  python _make_ai_pack.py                      打包到 AI_PACK/
  python _make_ai_pack.py --out DIR            指定输出目录
  python _make_ai_pack.py --memory PATH        显式指定 .workbuddy/memory 所在路径
"""
from __future__ import annotations

import collections
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HANDOFF = ROOT / "HANDOFF"
DOCS = ROOT / "app" / "docs"

# 项目外的工作记忆默认位置（换机或用别的工作区时可用 --memory 覆盖）
DEFAULT_MEMORY = Path(
    r"C:\Users\Admin\WorkBuddy\2026-09-22-22-14-43\.workbuddy\memory"
)

# 关键契约：零背景 AI 靠它们理解"接口约定是什么"
CONTRACTS = [
    "endpoint_contract.txt",
    "delivery_contract.txt",
    "link_experiment_contract.txt",
    "metric_definitions.json",
]


def copy_dir(src: Path, dst: Path, suffix: str | None = None) -> list[tuple[str, int]]:
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        if suffix and p.suffix.lower() not in (suffix, ".json", ".md", ".txt"):
            continue
        shutil.copy2(p, dst / p.name)
        copied.append((f"{dst.name}/{p.name}", p.stat().st_size))
    return copied


def write_manifest(out: Path, rows: list[tuple[str, int]]) -> None:
    lines = ["接手知识包内容清单", f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for name, size in rows:
        lines.append(f"  {size:>9,d} B   {name}")
    lines += [
        "",
        "给新 AI 的最小读法：只需先看 00_先读_给接手AI的总纲.txt（已按裁决优先级合并）。",
        "冲突时以 HANDOFF/10_遗留问题裁决与执行补充.txt 的表述为准。",
        "机器可读部分看 HANDOFF/context_snapshot.json。",
    ]
    (out / "文件清单.txt").write_text("\n".join(lines), encoding="utf-8")
    return None


# ── 文本质量自检 ──────────────────────────────────────────────────────────────
# 为什么需要：过去几版交接文档里混进过乱码/错词（如"疑 radical 场景""butterflies 指标"），
# 这类污染对零背景读者是致命的——它会以为那是术语。这里做自动预警。
_CJK = "\u4e00-\u9fff"
_TOKEN_CTX = re.compile(r"[A-Za-z][A-Za-z]{2,}")
_PATHISH = re.compile(r"[A-Za-z0-9_\\/-]")  # 标识符/路径边界；句点不算，否则放过错字
# 领域缩写与技术词白名单：它们确实只出现一两次，但不是错字
_ALLOW = {
    "txt", "json", "http", "https", "div", "span", "cmd", "api", "csv", "png", "jpg",
    "node", "git", "zip", "usb", "elf", "bit", "hdf", "xsa", "tcl", "svg", "html",
    "com", "python", "pyserial", "openocd", "vivado", "xsct", "ping", "cdp", "echo",
    "sha", "headless", "remote", "debugging", "port", "loopback", "app",
    # 通信/工程缩写
    "mio", "ddr", "tdma", "snr", "awgn", "ber", "evm", "pdp", "rms", "los", "nlos",
    "iq", "llp", "udp", "tcp", "fft", "fir", "lte", "bpsk", "dbpsk", "qpsk", "arm",
    "pl", "ps", "rtl", "sdk", "ip", "fpga", "pll", "bram", "lut", "ff", "dma", "irq",
    "spi", "uart", "jtag", "dsp", "src", "dst", "cfg", "dbg", "log", "msg", "ack",
    # 以下是本项目里真实存在的标识符/工具名，经人工确认不是错字（2026-10-31）
    "application", "client", "devcfg", "gpp", "installer", "install", "linkcond",
    "lts", "mavlink", "makefile", "powershell", "ram", "readme", "runtimeerror",
    "userprofile", "valueerror", "web", "winerror", "block", "canvas", "channelsource",
    "clear", "comm", "connected", "continuous", "diff", "duration", "enable",
    "fading", "false", "footer", "globalhealth", "hash", "history", "impactat",
    "jsdom", "mapperspective", "mediakey", "needsscroll", "not", "npm", "pctfmt",
    "phylab", "platform", "remove", "rendermedia", "return", "returnlive", "rounds",
    "rxstudy", "seconds", "selfcheck", "sessionstorage", "sigma", "sourcebar",
    "trace", "vendored", "maps", "usability", "cjs", "mjs", "rev", "details", "scrolls",
    "full", "manifest", "head", "core", "evidence", "mode", "list", "verify", "apply", "clone", "commit",
    "style", "themed", "updatedoppler", "railfold", "ivfix", "doppler",
    "amd", "systemverilog", "tap", "project", "source", "tab", "faults",
    "pagescroll", "viewport", "needsscroll", "dist", "offenders", "total", "fonts",
    "minimaps", "topo", "bees", "evidence", "mission", "rail", "hdr", "below",
}


def scan_quality(paths: list[Path]) -> list[tuple[str, int, str, str]]:
    """启发式：某个英文词在整个知识包里只出现一次，却和中文出现在同一行，就很可疑。

    判据为什么不写成"紧贴中文"：实际遇到的污染是 "含疑 radical 场景" 这种词间还有
    空格的形式，紧贴式匹配会漏掉它——第一版就因为这个缺陷误报"质检通过"。
    现在改为：整包只出现一次 + 该行含中文 = 可疑。技术术语在一百多页文档里通常会
    重复出现，因此单次出现的词几乎都是错字。结论仍是**提示性**的，需人工确认。
    """
    docs = []
    for p in paths:
        try:
            docs.append((p, p.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            continue
    counter = collections.Counter()
    for _, text in docs:
        for line in text.splitlines():
            counter.update(w.lower() for w in _TOKEN_CTX.findall(line))

    findings = []
    for p, text in docs:
        for no, line in enumerate(text.splitlines(), 1):
            if not re.search(f"[{_CJK}]", line):
                continue
            for mt in _TOKEN_CTX.finditer(line):
                w = mt.group(0)
                lw = w.lower()
                if lw in _ALLOW or counter[lw] != 1:
                    continue
                before = line[mt.start() - 1] if mt.start() else " "
                after = line[mt.end()] if mt.end() < len(line) else " "
                if _PATHISH.match(before) or _PATHISH.match(after):
                    continue  # 是文件名/标识符的一部分，不是独立词
                findings.append((p.name, no, w, line.strip()[:72]))
    return sorted(findings)



def build_master(out: Path, parts: list[tuple[str, Path]]) -> Path:
    """把关键文档合并成一个单文件，方便整个粘贴给新的 AI 会话。"""
    lines = [
        "=" * 74,
        "蜂群信道模拟器项目 —— 接手总纲（单文件版）",
        "这份文件是给对本工程一无所知的 AI/同学看的，读完应当能够独立接手。",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 74,
        "",
        "阅读建议：",
        "  1) 先通读本文件，建立全貌；",
        "  2) 接着看 HANDOFF/07_项目全史与当前状态.txt（最全的一份）；",
        "  3) 动手前用 HANDOFF/00_开始与复现.txt 核对环境能否跑起来。",
        "",
    ]
    for title, path in parts:
        lines += ["", "=" * 74, f"【附件】{title}", "=" * 74, ""]
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            body = f"（读取失败：{exc}）"
        lines.append(body.rstrip())
        lines.append("")

    master = out / "00_先读_给接手AI的总纲.txt"
    master.write_text("\n".join(lines), encoding="utf-8")
    return master


def main() -> int:
    args = sys.argv[1:]
    out = ROOT / "AI_PACK"
    mem = DEFAULT_MEMORY
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])
    if "--memory" in args:
        mem = Path(args[args.index("--memory") + 1])

    rows: list[tuple[str, int]] = []

    # 1) HANDOFF 全套
    handoff_dst = out / "HANDOFF"
    handoff_dst.mkdir(parents=True, exist_ok=True)
    for src_file in sorted(HANDOFF.glob("*.txt")) + sorted(HANDOFF.glob("*.json")):
        shutil.copy2(src_file, handoff_dst / src_file.name)
        rows.append((f"HANDOFF/{src_file.name}", src_file.stat().st_size))

    # 2) 根目录接手入口
    entry = ROOT / "AI_START_HERE.txt"
    if entry.exists():
        shutil.copy2(entry, out / entry.name)
        rows.append((entry.name, entry.stat().st_size))

    # 3) 项目外的工作记忆快照（这一步是防遗漏的关键）
    mem_rows = 0
    mem_dst = out / "memory_snapshot"
    mem_dst.mkdir(parents=True, exist_ok=True)
    if mem.is_dir():
        for p in sorted(mem.iterdir()):
            if p.is_file() and p.suffix in (".md", ".txt"):
                shutil.copy2(p, mem_dst / p.name)
                rows.append((f"memory_snapshot/{p.name}", p.stat().st_size))
                mem_rows += 1
    else:
        warn = (out / "memory_snapshot" / "未找到工作记忆.txt")
        warn.write_text(
            f"未在 {mem} 找到 .workbuddy/memory。\n"
            "该目录不在项目内，换机器时容易漏拷。请用 --memory 指向它的真实位置后重新打包。\n",
            encoding="utf-8",
        )
        rows.append(("memory_snapshot/未找到工作记忆.txt", warn.stat().st_size))

    # 4) 关键契约
    for name in CONTRACTS:
        p = DOCS / name
        if p.exists():
            (out / "docs_contracts").mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out / "docs_contracts" / name)
            rows.append((f"docs_contracts/{name}", p.stat().st_size))

    # 5) 单文件总纲（放在最后，内容基于已落盘的文件）
    #    顺序即"裁决优先"顺序：10 是对旧文档各种自相矛盾的最终裁决，必须排最前
    master_parts = [
        ("HANDOFF/10 遗留问题裁决与执行补充（冲突时以此为准）",
         out / "HANDOFF" / "10_遗留问题裁决与执行补充.txt"),
        ("HANDOFF/09 接手执行清单与已知陷阱", out / "HANDOFF" / "09_接手执行清单与已知陷阱.txt"),
        ("HANDOFF/07 项目全史与当前状态", out / "HANDOFF" / "07_项目全史与当前状态.txt"),
        ("HANDOFF/08 UI 现状与技术债", out / "HANDOFF" / "08_UI现状与技术债.txt"),
        ("HANDOFF/06 跨机迁移与 PL 重建", out / "HANDOFF" / "06_跨机迁移与PL重建.txt"),
        ("HANDOFF/00 开始与复现", out / "HANDOFF" / "00_开始与复现.txt"),
        ("HANDOFF/01 工程导航", out / "HANDOFF" / "01_工程导航.txt"),
        ("HANDOFF/02 接口与边界", out / "HANDOFF" / "02_接口与边界.txt"),
        ("HANDOFF/03 验收与后续开发", out / "HANDOFF" / "03_验收与后续开发.txt"),
        ("HANDOFF/04 迁移检查结果", out / "HANDOFF" / "04_迁移检查结果.txt"),
        ("HANDOFF/05 本次更新与限制", out / "HANDOFF" / "05_本次更新与限制.txt"),
    ]
    master_parts = [(t, p) for t, p in master_parts if p.exists()]
    for p in sorted(handoff_dst.glob("*.txt")):
        if all(p != q for _, q in master_parts):
            master_parts.append((f"HANDOFF/{p.name}", p))
    mem_files = sorted((out / "memory_snapshot").glob("*.md"))
    for p in mem_files:
        master_parts.append((f"工作记忆/{p.name}", p))
    master = build_master(out, master_parts)

    write_manifest(out, rows + [("00_先读_给接手AI的总纲.txt", master.stat().st_size)])

    print("=" * 66)
    print("接手知识包已生成：", out)
    print("=" * 66)
    for name, size in rows:
        print(f"  {size:>9,d}  {name}")
    print(f"\n  {master.stat().st_size:>9,d}  00_先读_给接手AI的总纲.txt  ← 粘贴给新 AI 用这份")
    print(f"\n  工作记忆快照：{'已纳入 ' + str(mem_rows) + ' 个文件' if mem_rows else '未找到，请确认路径'}")

    # 6) 文本质量自检：把可能的乱码在交付前拦下来
    #    只扫描「源文件」：总纲是它们的副本，一起统计会让每个词都变成出现 2 次以上，
    #    从而把所有污染都洗白（第一版就踩过这个坑）。
    #    范围只限 HANDOFF/ 与入口文件：日常工作记忆是流水账，里面一次性英文术语本来就多，
    #    用这个词频法会全是误报，扫它没有意义（不在监控范围内 ≠ 没问题）。
    #    范围只限 HANDOFF/ 与入口文件：工作记忆与契约是流水账/命令名清单，里面一次性英文
    #    标记本来就多（HNRESET、NETSTEP 之类），用这个词频法会全是误报。
    #    扫不了不等于没问题 —— 那两类文件靠零背景试读验证。
    packed = list(handoff_dst.glob("*.txt")) + [out / "AI_START_HERE.txt"]
    dirty = scan_quality([p for p in packed if p.exists()])
    if dirty:
        print("\n  !! 文本质检：发现可疑词（在整包中只出现一次且紧贴中文），请人工确认：")
        for name, no, w, snippet in dirty[:15]:
            print(f"     - {name}:{no}  「{w}」  {snippet}")
        if len(dirty) > 15:
            print(f"     …另有 {len(dirty) - 15} 处")
    else:
        print("\n  文本质检通过：未发现疑似乱码/错词")

    print("\n  推荐给新 AI 的开场白：")
    print('    "请先完整阅读这份《给接手AI的总纲》，然后向我复述：')
    print('     ①本项目的真实边界（哪些是真的、哪些是模拟的）；')
    print('     ②P1–P5 各自需要什么工具才能完成；')
    print('     ③六条红线分别对应什么教训。"')
    print("     复述错误的，说明没读懂，请它重读后再动手。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
