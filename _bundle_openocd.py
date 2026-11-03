# -*- coding: utf-8 -*-
"""把 JTAG 工具套件收纳进项目，使整包自包含、可迁移到任意路径或其他机器。

背景
----
`app/tools/server.py` 在没有 Xilinx SDK 时回退到 OpenOCD 经板载 FT2232H 加载同一份
bit/init/elf。原先这套工具与本项目的 JTAG 配置散落在项目之外的 D:\\SwarmLab\\tools 下，
导致只拷贝项目目录到新机器后「连不上板」。本脚本把它们收进项目内 app/openocd/，
配合 server.py 的三级路径解析，实现搬过去就能直接用。

收纳内容
--------
  openocd/                OpenOCD 可执行程序与自带 scripts（xpack-openocd-0.12.0-7）
  swarm_ft2232.cfg        适配本板 FT2232H 的接口配置（server.py 加载链用到）
  ps7_shim.tcl            PS7 初始化衔接
  swarm_load.cfg          PCAP 加载序列
  reset_board.cfg         复位辅助（可选，转换/OpenOCD 复位调试用）
  zadig.exe               JTAG 驱动切换工具（libusb_open 失败时需要）

用法
----
  python _bundle_openocd.py              # 收纳（已存在则跳过，除非 --force）
  python _bundle_openocd.py --force      # 覆盖重新收纳
  python _bundle_openocd.py --check      # 只检查是否已自包含

收纳完成后，即使换机器、换盘符，server.py 会自动优先使用项目内的这套工具；
也可用环境变量 SWARM_OPENOCD_TOOLS / SWARM_OPENOCD 指向其他位置覆盖。
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
DEST = APP / "openocd"

# 作者本机上的外部工具根目录；在新机器上若位置不同，改这里或直接用环境变量指向
EXTERNAL = Path(os.environ.get("SWARM_OPENOCD_SRC", r"D:\SwarmLab\tools"))

NEEDED_FILES = [
    "swarm_ft2232.cfg",
    "ps7_shim.tcl",
    "swarm_load.cfg",
    "zadig.exe",
    # PCAP 镜像：原先硬编码在 swarm_load.cfg 里指向项目外路径，
    # 不收纳就会出现「换机器后 OpenOCD 报 couldn't open ..._pcap.bin」
    "system_wrapper_pcap.bin",
]
OPTIONAL_FILES = [
    "reset_board.cfg",
    "pl_jstart.cfg",
    "probe.cfg",
]


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else 0


def check() -> bool:
    """检查项目是否已经自包含 JTAG 工具链。"""
    exe = DEST / "openocd" / "xpack-openocd-0.12.0-7" / "bin" / "openocd.exe"
    missing = [f for f in NEEDED_FILES if not (DEST / f).exists()]
    print("JTAG 工具自包含状态：")
    print(f"  目标目录     : {DEST}")
    print(f"  openocd.exe  : {'已就位' if exe.exists() else '缺失'}")
    print(f"  scripts 目录 : {'已就位' if (DEST/'openocd'/'xpack-openocd-0.12.0-7'/'openocd'/'scripts').exists() else '缺失'}")
    print(f"  必备配件     : {'全部齐全' if not missing else '缺 ' + ', '.join(missing)}")
    if DEST.exists():
        print(f"  占用体积     : {human(dir_size(DEST))}")
    ok = exe.exists() and not missing
    print(f"  结论         : {'可随项目整体迁移' if ok else '尚不自包含，请执行 python _bundle_openocd.py'}")
    return ok


def bundle(force: bool) -> int:
    if not EXTERNAL.is_dir():
        print(f"未找到外部工具目录：{EXTERNAL}")
        print("请设置环境变量 SWARM_OPENOCD_SRC 指向含 openocd/ 与各 cfg/tcl 的目录后重试。")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)
    total = 0

    # 1) OpenOCD 主程序树
    src_tree = EXTERNAL / "openocd"
    dst_tree = DEST / "openocd"
    if src_tree.is_dir():
        if dst_tree.exists() and force:
            shutil.rmtree(dst_tree)
        if not dst_tree.exists():
            shutil.copytree(src_tree, dst_tree)
            total += dir_size(dst_tree)
            print(f"  收纳 openocd 主程序 : {human(dir_size(dst_tree))}")
        else:
            print("  openocd 主程序已存在，跳过（--force 可覆盖）")
    else:
        print(f"  [警告] 源未含 openocd/ 子树：{src_tree}")

    # 2) 配置文件与工具
    for name in NEEDED_FILES + OPTIONAL_FILES:
        src = EXTERNAL / name
        dst = DEST / name
        if not src.is_file():
            tag = "[警告]" if name in NEEDED_FILES else "[可选]"
            print(f"  {tag} 源缺失，跳过：{name}")
            continue
        if dst.exists() and not force:
            print(f"  已存在，跳过：{name}")
            continue
        shutil.copy2(src, dst)
        total += dst.stat().st_size
        print(f"  收纳 {name:20s} : {human(dst.stat().st_size)}")

    print(f"\n收纳完成 -> {DEST}（本次写入 {human(total)}）")
    print("server.py 会自动优先使用项目内这套工具；换机器无需再改任何绝对路径。")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return 0 if check() else 1
    print("=" * 58)
    print("把 JTAG 工具套件收纳进项目（使整包自包含可迁移）")
    print("=" * 58)
    rc = bundle("--force" in sys.argv)
    if rc == 0:
        print()
        check()
    return rc


if __name__ == "__main__":
    sys.exit(main())
