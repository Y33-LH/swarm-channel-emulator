"""把「项目本体」整理成一个可直接拷走 / 可直接在新机器运行的自包含目录。

背景
----
本机目录 D:\\Swarm_20261023_step29 总量约 1.8 GB，但里面混着三类东西：
  ① 运行必需（源码、便携 Python、JTAG 工具、固件镜像）
  ② 历史产物（288 次实板实验记录 239 MB）
  ③ 垃圾与临时输出（__pycache__、日志、一次性探测脚本的输出）

若不分拣，要么抱着 1.8 GB 硬拷，要么用 git clone 得到一个**完全过时的版本**
——因为当前所有改动都还在工作区：31 条已跟踪改动 + 31 条未跟踪新增，都没进 HEAD。
本脚本的目的就是把「搬什么」变成一个可选、可解释、可校验的动作。

三种模式
--------
  core      运行必需，约 260 MB。到新机器即可起服务、连板、跑实验。
  evidence  core + app/results（历史实板实验证据，+239 MB）。要做答辩取证时选。
  full      evidence + assistant/*.gguf（本地问答模型，+610 MB）。非核心，一般不带。

用法
----
  runtime/python/python.exe _make_project_bundle.py              # core
  runtime/python/python.exe _make_project_bundle.py --mode evidence
  runtime/python/python.exe _make_project_bundle.py --.git       # 额外带上 .git（593 MB）
  runtime/python/python.exe _make_project_bundle.py --verify     # 对已生成的包做自检
  runtime/python/python.exe _make_project_bundle.py --list       # 只打印分拣表，不拷贝
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "PROJECT_BUNDLE"

# ── 分拣规则 ────────────────────────────────────────────────────────────────
# (类别, 相对路径 glob 或具体文件)。顺序无关，靠 CATEGORY_ORDER 决定展示次序。
RULES: list[tuple[str, str, str]] = [
    # 类别, 模式, 说明 —— 下面是具体归属
]

CORE_FILES = [
    "START.cmd", "BUILD.cmd", "TEST_SOFTWARE.cmd", "REFRESH_DEV.cmd",
    "build.ps1", "dev_settings.ps1",
    "launcher.py", "portable_server.py", "refresh_dev.py", "test_software.py",
    "verify_ux.py", "find_board_port.py",
    "config.json", "PACKAGE_SHA256.json", ".gitignore",
    "AI_START_HERE.txt",
    # 常驻工具脚本（gitignore 里点名排除的那几个临时探测脚本不在此列）
    "_resign_release.py", "_export_handover.py", "_bundle_openocd.py",
    "_check_openocd.py", "_make_ai_pack.py", "_make_project_bundle.py",
    "_run_experiment.py", "_run_severe.py", "_audit_controls.py",
    "_bench_batch.py", "_verify_improvements.py",
]

CORE_DIRS = [
    "app/docs", "app/hw", "app/rtl", "app/sw", "app/tests", "app/tools",
    "app/ui", "app/reference", "app/configs", "app/exports", "app/media",
    "app/openocd", "app/ready",
    "HANDOFF", "AI_PACK",
    "runtime",
    "licenses", "provenance", "validation",
]

CORE_FILES_IN_APP_ROOT = [
    "app/release.json",
]

EVIDENCE_DIRS = ["app/results"]
FULL_DIRS = ["assistant"]

GIT_DIR = ".git"

# 任何模式都排除：可再生或纯临时
EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", "node_modules"}
EXCLUDE_SUFFIX = {".pyc", ".log"}
EXCLUDE_FILES = {
    "_severe_out.txt", "_verify_out.txt", "_last_run.json",
    "_severe_result.json", "_verify_improvements.json",
    "_audit_controls.json", "_bench_batch_result.json",
    "_probe_board.py", "_sim_selfcheck.mjs", "_smoke_dom.mjs",
    "web_stdout.log", "web_stderr.log",
}

CATEGORY_NOTE = {
    "app/tools": "上位机服务端 + 场景/指标计算（含 server.py）",
    "app/ui": "前端三页 UI（index.html 与各模块 JS/CSS）",
    "app/sw": "ARM 端 C 源码（本次 P1 要重编的就是它）",
    "app/rtl": "PL 端 SystemVerilog 源码（P3 多径扩展要改这里）",
    "app/hw": "Vivado 批处理脚本与板卡约束",
    "app/ready": "固件产物：bit / ps7_init.tcl / ELF",
    "app/openocd": "JTAG 工具套件（含 PCAP 镜像、Zadig），替代 SDK 下载固件",
    "app/docs": "设计/冻结/交接契约文档",
    "app/tests": "验收脚本与 UI 布局探测脚本",
    "app/reference": "接收端参考向量（用于 selfcheck 比对）",
    "app/configs": "用户保存的配置预设",
    "app/exports": "实验导出 CSV/HTML",
    "app/media": "业务回放素材（音/视频源）",
    "app/results": "历史实板实验证据（每次一个目录，含 program.log/metadata）",
    "runtime": "便携 Python（含 vendored pyserial），新机器免装 Python/pip",
    "HANDOFF": "人机交接文档 00–10",
    "AI_PACK": "给新 AI 的接手知识包（总纲 + 记忆快照）",
    "assistant": "本地问答模型 Qwen3-0.6B（.gguf 610 MB，非核心）",
    "licenses": "运行时与第三方许可证",
    "provenance": "打包溯源与冻结验收记录",
    "validation": "软件/可移植性验证日志",
}


def plan(mode: str, with_git: bool) -> list[tuple[str, str]]:
    """返回 [(源相对路径, 类别)]。"""
    items: list[tuple[str, str]] = []
    for rel in CORE_FILES + CORE_FILES_IN_APP_ROOT:
        if (ROOT / rel).exists():
            items.append((rel, "root"))
    for d in CORE_DIRS:
        if (ROOT / d).is_dir():
            items.append((d, d))
    if mode in ("evidence", "full"):
        for d in EVIDENCE_DIRS:
            if (ROOT / d).is_dir():
                items.append((d, d))
    if mode == "full":
        for d in FULL_DIRS:
            if (ROOT / d).is_dir():
                items.append((d, d))
    if with_git and (ROOT / GIT_DIR).is_dir():
        items.append((GIT_DIR, GIT_DIR))
    return items


def _ignore(rel_top: str):
    def _fn(directory: str, names: list[str]) -> set[str]:
        drop = set()
        for n in names:
            if n in EXCLUDE_NAMES or n in EXCLUDE_FILES:
                drop.add(n)
            elif Path(n).suffix in EXCLUDE_SUFFIX:
                drop.add(n)
        return drop
    return _fn


def dir_bytes(p: Path) -> tuple[int, int]:
    """返回 (文件数, 总字节)。已排除可再生垃圾，故与 du 结果略有差异属正常。"""
    n = total = 0
    for root, dirs, files in p.walk():
        dirs[:] = [d for d in dirs if d not in EXCLUDE_NAMES]
        for f in files:
            if f in EXCLUDE_FILES or Path(f).suffix in EXCLUDE_SUFFIX:
                continue
            try:
                total += (Path(root) / f).stat().st_size
                n += 1
            except OSError:
                pass
    return n, total


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0
    return f"{n:.1f} GB"


def show_plan(mode: str, with_git: bool) -> None:
    items = plan(mode, with_git)
    print(f"模式 {mode}{'  (+.git)' if with_git else ''}  分拣表：")
    print(f"  {'条目':<20} {'文件数':>8} {'体积':>12}   说明")
    print("  " + "-" * 88)
    grand_n = grand_b = 0
    for rel, cat in items:
        p = ROOT / rel
        if p.is_file():
            n, b = 1, p.stat().st_size
        else:
            n, b = dir_bytes(p)
        grand_n += n
        grand_b += b
        note = CATEGORY_NOTE.get(rel, "（顶层 app 文件）" if rel.startswith("app/") else "顶层脚本/入口")
        print(f"  {rel:<20} {n:>8,} {human(b):>12}   {note}")
    print("  " + "-" * 88)
    print(f"  {'合计':<20} {grand_n:>8,} {human(grand_b):>12}")
    print("\n  排除：__pycache__ / *.pyc / *.log / 一次性探测脚本与其输出")
    if mode == "core":
        print("  未含：app/results（历史实验证据，用 --mode evidence 带上）")
    if mode in ("core", "evidence"):
        print("  未含：assistant/*.gguf 本地问答模型（非核心，用 --mode full 带上）")
    if not with_git:
        print("  未含：.git（593 MB，且 HEAD 停在 99edf08，不含本轮任何改动 —— 详见下方警告）")


GIT_WARNING = """
★★ 重要：不要用 git clone/pull 来搬运这个项目 ★★

当前 HEAD = 99edf08（2026-10-23 之前的状态），而工作区里有：
    · 31 条已跟踪文件的改动（含 app/sw/*.c、app/ui/*、app/tools/server.py、release.json）
    · 31 条未跟踪的新增（含 HANDOFF/06–10、三个便携化脚本、app/openocd/、多数 UI 模块）
也就是说：**这十来天的全部工作都还没进版本库**。
如果在新机器上 clone 这个仓库，拿到的是一个过时的、缺 Ray/Rician 之外的全部近期整改的版本。
必须用本 bundle（目录拷贝）搬运，到新机器后再决定是否 commit。
"""


def write_readme(dst: Path, mode: str, with_git: bool, rows: list[tuple[str, int, str]]) -> None:
    lines = [
        "SwarmLab 蜂群信道模拟器 —— 新机器开箱指南",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"模式：{mode}{'  (+.git)' if with_git else ''}",
        "",
        "【第 0 步：先给要接手的 AI 读什么】",
        "  把 AI_PACK/00_先读_给接手AI的总纲.txt 整个喂给它，然后问：",
        "  「请复述 P1–P5 各自需要什么工具，以及 R1–R7 七条红线。」",
        "  答错就说明它没读懂，别让它动手。",
        "",
        "【第 1 步：环境】",
        "  不需要安装 Python —— runtime/python 是便携解释器，依赖已 vendored 在 app/tools/python_deps。",
        "  不需要联网 —— JTAG 工具已收纳在 app/openocd。",
        "  需要一次驱动安装：新机器首次连板，右键管理员运行 app/openocd/zadig.exe，",
        "  把 FT2232H 的 Interface 0 切到 WinUSB（否则 OpenOCD 报 libusb_open 失败）。",
        "",
        "【第 2 步：起服务】",
        "  在项目根目录下用便携解释器执行（PowerShell 示例，COM 号按本机改）：",
        "    $env:SWARM_BOARD_PROFILE='wildfire7020'",
        "    $env:SWARM_XSCT=''                       # 留空 = 没有 SDK，走 OpenOCD 回退",
        "    .\\runtime\\python\\python.exe -X utf8 -B portable_server.py --http 18878 --port COM5",
        "  缺 SWARM_BOARD_PROFILE 会被 server.py 直接拒绝加载（RuntimeError），这是硬要求。",
        "",
        "【第 3 步：连板】",
        "  浏览器打开 http://127.0.0.1:18878/ ，点「烧写/连接」。",
        "  固件经 JTAG 加载进 DDR，掉电即失 —— 重启板子要重新加载，这是正常的。",
        "",
        "【第 4 步：改完核心文件必须重签】",
        "  改动 app/ui/*、app/tools/*、app/release.json 等受保护文件后，必须跑：",
        "    runtime\\python\\python.exe _resign_release.py",
        "  否则发布校验会拦截实验（你会在事件里看到「校验失败」）。",
        "",
        GIT_WARNING,
        "",
        "【本次打包内容清单】",
    ]
    for name, size, digest in rows:
        lines.append(f"  {human(size):>10}  {digest}  {name}")
    lines += [
        "",
        "完整性校验：在新机器上跑",
        "  runtime\\python\\python.exe _make_project_bundle.py --verify",
        "可对包内每个文件重算 SHA256 并与 MANIFEST.sha256 比对。",
    ]
    (dst / "00_新机器开箱指南.txt").write_text("\n".join(lines), encoding="utf-8")


def build(mode: str, with_git: bool, no_clean: bool = False) -> None:
    if OUT.exists() and not no_clean:
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    items = plan(mode, with_git)
    rows: list[tuple[str, int, str]] = []
    total_b = 0
    t0 = time.time()
    for rel, _cat in items:
        src, dst = ROOT / rel, OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, dst)
        else:
            shutil.copytree(src, dst, ignore=_ignore(rel), dirs_exist_ok=True)
        n, b = (1, src.stat().st_size) if src.is_file() else dir_bytes(src)
        total_b += b
        print(f"  ✓ {rel:<20} {n:>6,} 个文件  {human(b):>10}")
    # 清单 + 摘要：对每个交付文件算 sha256
    print("\n正在为每个文件计算 SHA256（用于到新机器后校验搬运完整性）…")
    # 自生成的三件（指南/清单/MANIFEST）在收集之后还会被改写，必须排除，否则自指哈希必然不符
    self_generated = {"00_新机器开箱指南.txt", "文件清单.csv", "MANIFEST.sha256"}
    for f in sorted(OUT.rglob("*")):
        if f.is_file() and f.name not in self_generated:
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            rows.append((str(f.relative_to(OUT)).replace("\\", "/"), f.stat().st_size, h))
    write_readme(OUT, mode, with_git, rows)
    (OUT / "文件清单.csv").write_text(
        "\n".join(["路径,字节,SHA256"] + [f"{n},{s},{d}" for n, s, d in rows]),
        encoding="utf-8")
    (OUT / "MANIFEST.sha256").write_text(
        "\n".join(f"{d}  {n}" for n, _s, d in rows), encoding="utf-8")
    print(f"\n完成 → {OUT}")
    print(f"  文件 {len(rows):,} 个，合计 {human(total_b)}，耗时 {time.time() - t0:.1f}s")


def verify() -> None:
    if not OUT.exists():
        print("还没有生成过包，先跑一次 _make_project_bundle.py"); return
    manifest = OUT / "MANIFEST.sha256"
    if not manifest.exists():
        print("缺 MANIFEST.sha256"); return
    bad = missing = 0
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split("  ", 1)
        f = OUT / name
        if not f.exists():
            missing += 1; continue
        if hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            bad += 1
        checked += 1
    # 关键文件存在性自检 —— 决定「到新机器能不能跑起来」
    keys = [
        "runtime/python/python.exe", "portable_server.py", "START.cmd",
        "app/tools/server.py", "app/tools/python_deps/serial/__init__.py",
        "app/ui/index.html", "app/ready/swarm_app.elf", "app/ready/system_wrapper.bit",
        "app/openocd/swarm_load.cfg", "app/openocd/system_wrapper_pcap.bin",
        "app/release.json", "_resign_release.py",
        "HANDOFF/10_遗留问题裁决与执行补充.txt", "AI_PACK/00_先读_给接手AI的总纲.txt",
    ]
    print(f"=== 包自检 {OUT} ===")
    print(f"  清单条目 {checked} 个：缺失 {missing}，哈希不符 {bad}")
    print("  --- 关键文件 ---")
    for k in keys:
        print(f"    {'OK ' if (OUT / k).exists() else '缺失'}  {k}")
    ok = missing == 0 and bad == 0 and all((OUT / k).exists() for k in keys)
    print(f"\n  结论：{'可以整包拷到新机器' if ok else '不完整，不要拷走'}")


def main() -> None:
    ap = argparse.ArgumentParser(description="整理项目本体为可搬运的自包含目录")
    ap.add_argument("--mode", choices=("core", "evidence", "full"), default="core")
    ap.add_argument("--git", action="store_true", help="额外带上 .git（593 MB，且 HEAD 是旧状态）")
    ap.add_argument("--list", action="store_true", help="只打印分拣表")
    ap.add_argument("--verify", action="store_true", help="校验已生成的包")
    ap.add_argument("--no-clean", action="store_true",
                    help="不清空旧包，只增量覆盖（改了少量文件后刷新包时使用；"
                         "源里已删掉的文件不会从包里消失）")
    a = ap.parse_args()

    if a.verify:
        verify(); return
    if a.list:
        show_plan(a.mode, a.git); print(GIT_WARNING); return
    print(f"=== 整理项目本体（模式 {a.mode}）===\n")
    build(a.mode, a.git, a.no_clean)
    print(GIT_WARNING)


if __name__ == "__main__":
    main()
