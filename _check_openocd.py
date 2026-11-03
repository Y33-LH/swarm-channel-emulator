# -*- coding: utf-8 -*-
"""验证 JTAG 回退工具能否正确解析到——新机器上第一件事就跑它。

为什么要有这个脚本：
  server.py 在没有 Xilinx SDK 时，会用 OpenOCD 经板载 FT2232H 加载 bit/init/elf。
  工具位置原先写死在作者本机路径，搬到别的机器/别的盘符就会连不上板。
  现在改成三级解析后，这个脚本直接调用真实的 resolve_openocd()，
  连 scenarios 一起验证（默认、环境变量覆盖），不用改一次代码猜一次。

用法：
  python _check_openocd.py
退出码 0 表示解析正常且必备配件齐全；非 0 说明需要收纳或设置环境变量。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
sys.path[:0] = [str(APP / "tools"), str(APP / "tools" / "python_deps")]

try:
    import server
except Exception as exc:  # 依赖缺失或路径不对时给出可执行指引，而不是抛裸异常
    print(f"无法导入 server.py：{exc}")
    print("请在项目根目录下运行本脚本，并确认 app/tools/python_deps 存在。")
    sys.exit(2)

NEED_IN_TOOLS = ["swarm_ft2232.cfg", "ps7_shim.tcl", "swarm_load.cfg"]
SCRIPTS_REL = "openocd/xpack-openocd-0.12.0-7/openocd/scripts"


def report(tag: str) -> bool:
    tools, exe = server.resolve_openocd()
    print(f"\n[{tag}]")
    if not tools:
        print("  工具目录  : 未找到")
        print("  可执行文件: 未找到")
        return False
    missing = [f for f in NEED_IN_TOOLS if not (Path(tools) / f).is_file()]
    scripts = Path(tools) / SCRIPTS_REL
    print(f"  工具目录  : {tools}")
    print(f"  可执行文件: {exe if exe else '未找到'}")
    print(f"  scripts   : {'已就位' if scripts.is_dir() else '缺失 -> ' + str(scripts)}")
    print(f"  必备配件  : {'齐全' if not missing else '缺 ' + ', '.join(missing)}")
    ok = bool(exe) and scripts.is_dir() and not missing
    print(f"  判定      : {'OK 可直接连板加载' if ok else '不可用'}")
    return ok


def main() -> int:
    print("=" * 60)
    print("JTAG 回退工具解析自检（决定换机器后能不能连板）")
    print("=" * 60)

    # 场景一：默认（应命中项目自带 app/openocd/）
    saved = (os.environ.get("SWARM_OPENOCD_TOOLS"), os.environ.get("SWARM_OPENOCD"))
    os.environ.pop("SWARM_OPENOCD_TOOLS", None)
    os.environ.pop("SWARM_OPENOCD", None)
    ok_default = report("默认：项目自带")

    # 场景二：环境变量覆盖（模拟换机器后工具放在别处）
    ok_env = True
    sentinel = APP / "openocd"          # 故意指向同一目录，验证优先级通路可走通
    os.environ["SWARM_OPENOCD_TOOLS"] = str(sentinel)
    os.environ["SWARM_OPENOCD"] = str(sentinel / "openocd/xpack-openocd-0.12.0-7/bin/openocd.exe")
    tools_e, exe_e = server.resolve_openocd()
    ok_env = tools_e == sentinel and exe_e is not None and exe_e.is_file()
    print(f"\n[环境变量覆盖]")
    print(f"  SWARM_OPENOCD_TOOLS -> {tools_e}")
    print(f"  判定      : {'OK 环境变量优先生效' if ok_env else 'FAIL 环境变量未生效'}")

    # 还原
    if saved[0] is None:
        os.environ.pop("SWARM_OPENOCD_TOOLS", None)
    else:
        os.environ["SWARM_OPENOCD_TOOLS"] = saved[0]
    if saved[1] is None:
        os.environ.pop("SWARM_OPENOCD", None)
    else:
        os.environ["SWARM_OPENOCD"] = saved[1]

    print("\n" + "=" * 60)
    if ok_default and ok_env:
        print("结论：三级解析均正常，项目可整体搬运到任意路径/其他 Windows 机器。")
        return 0
    print("结论：存在不可用场景。请运行 python _bundle_openocd.py 收纳工具，"
          "或设置 SWARM_OPENOCD_TOOLS / SWARM_OPENOCD 指向正确位置。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
