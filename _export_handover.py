# -*- coding: utf-8 -*-
"""导出接手上下文快照 + 最小硬件构建包。

用途：当本机会话结束、需要把项目搬到另一台机器（如装有 Vivado/SDK 的机器）
继续开发时，运行本脚本，产出两样东西：

  1) HANDOFF/context_snapshot.json
     —— 新机器上的 AI 会话第一件事就是读这个文件，它包含：
        项目定位 / 当前达到状态 / 已确证的待办与卡点 / 固件知识（寄存器与换算）
        / 本机无法完成的事及其原因 / 到新机器后的建议动作顺序。
  2) build_handoff/rtl_build_<日期>/（可选，加参数 --rtl）
     —— 只含重建 PL 所需要的文件（RTL + Tcl + 板卡配置），几十 KB，
        拷到 Vivado 机器上即可直接跑综合，无需搬运 1.7 GB 全包。

用法：
  python _export_handover.py                 # 只生成上下文快照
  python _export_handover.py --rtl           # 另生成 RTL 最小构建包
  python _export_handover.py --rtl --zip     # 构建包额外打成 zip

原则：本脚本只读取现状、不臆造结论。任何"已支持/未支持"的判断都必须有
代码行证据，快照里每条事实都带 source 字段指向文件与行号。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
SW = APP / "sw"
RTL = APP / "rtl"
HW = APP / "hw"
READY = APP / "ready"
HANDOFF = ROOT / "HANDOFF"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def head_commit() -> dict:
    """读取 git HEAD，便于在新机器确认版本是否一致。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0:
            commit = out.stdout.strip()
            dirty = subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT,
                capture_output=True, text=True, timeout=20
            )
            n_modified = len([x for x in dirty.stdout.splitlines() if x.strip()])
            return {"commit": commit, "modified_entries": n_modified}
    except Exception:
        pass
    return {"commit": None, "modified_entries": None}


def artifact_state() -> dict:
    """核对固件源码与其构建产物谁更新——防止"源码改过但板上跑的还是旧 ELF"。"""
    pairs = [
        ("sw_source", SW / "scene_product.c"),
        ("elf", READY / "swarm_app.elf"),
        ("bitstream", READY / "system_wrapper.bit"),
        ("hdf", READY / "system.hdf"),
    ]
    out = {}
    for key, p in pairs:
        if p.exists():
            st = p.stat()
            out[key] = {
                "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
                "size": st.st_size,
                "sha256_head": sha256(p)[:16],
            }
        else:
            out[key] = None

    # 判断是否存在"源码比产物新"的情况
    src = out.get("sw_source")
    warn = []
    for key in ("elf", "bitstream"):
        art = out.get(key)
        if src and art and src["mtime"] > art["mtime"]:
            warn.append(
                f"{key} ({art['mtime']}) 早于 sw 源码 ({src['mtime']})，"
                f"板上/包内固件不是当前源码的编译产物，需要在 SDK 侧重新构建后再声明'来源统一'"
            )
    out["_sync_warning"] = warn
    return out


def scan_firmware_facts() -> dict:
    """从固件源码里抽取跨机开发必须复述的硬知识（都带行号证据）。"""
    facts = {}

    # 1) PL 版本寄存器：ELF 启动会校验，改协议号不动它就不会触发 WRONG_PL_VERSION
    src = (SW / "payload_driver.h").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"#define\s+SWARM_PL_VERSION\s+(\S+)", src)
    if m:
        facts["pl_version_register"] = {
            "value": m.group(1),
            "source": "app/sw/payload_driver.h",
            "note": "main.c 启动时用 rd(0x3c) 比对；只要不改这个常量，重编 ELF 后 PL bitstream 无需替换",
        }

    # 2) 载波 -> CFO 的换算与寄存器宽度，决定"载波能否安全开放到 6000 MHz"
    sc = (SW / "scene_product.c").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^\s*fc=cfg\[13\].*$", sc, re.M)
    if m:
        line = sc[: m.start()].count("\n") + 1
        facts["carrier_usage"] = {
            "source": f"app/sw/scene_product.c:{line}",
            "snippet": m.group(0).strip()[:160],
            "note": "载波频率 fc 仅参与多普勒 CFO 计算，PL 不接收 fc 本身，故放开 fc 上限不需要改 RTL",
        }
    m = re.search(r"limits=.*carrier_mhz[^\n]*", (APP / "tools" / "product_config.py").read_text(
        encoding="utf-8", errors="replace"))
    if m:
        facts["carrier_limits_python"] = {
            "source": "app/tools/product_config.py",
            "note": "Python 侧 carrier_mhz 允许区间见该行；固件侧 cfg[13] 校验上限在 scene_product.c 的 low/high 表"
        }

    nc = (SW / "network.c").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"wr\(92[^\n]*", nc)
    if m:
        line = nc[: m.start()].count("\n") + 1
        facts["cfo_register_width"] = {
            "source": f"app/sw/network.c:{line}",
            "note": "CFO 以 32 位相位步进字写入，量化式为 cfo*2^32/8e6；"
                    "8 MHz 采样下可表示 ±4 MHz。6000 MHz 载波配 20 m/s 上限速度时多普勒约 400 Hz，"
                    "远低于溢出门限，因此开放载波无需重建 PL",
        }

    # 3) 多径抽头数：这是真正被 RTL 写死的地方
    tp = (RTL / "two_path_link.sv").read_text(encoding="utf-8", errors="replace")
    delayed = re.findall(r"\bdelayed(\d)\b", tp)
    taps = sorted(set(delayed))
    facts["multipath_taps"] = {
        "source": "app/rtl/two_path_link.sv",
        "observed_tap_registers": taps,
        "note": "抽头数在 RTL 里写死（每级 delayedN/historyN/gain_holdN 各一套），"
                "扩展到 4 径属于 PL 逻辑改动，必须 Vivado 重新综合实现，无法用 ARM 侧替代",
    }

    # 4) 干预（注入）的生效方式——决定"自动到期"能否纯软件实现
    facts["injection_mechanism"] = {
        "source": "app/sw/network.c (config_link/scene_link) + app/sw/link_control.h (edge_apply)",
        "note": "每帧先由 scene_link 按几何重算信道参数，随后 edge_apply 在 ARM 侧叠乘用户注入的系数；"
                "enabled=0 时 edge_apply 直接返回，固件内没有回滚/undo 代码。"
                "因此'注入到期自动解除'完全可在 ARM C 里加 TTL 计数器实现，不需要改动 PL",
    }

    # 5) 场景剧本（务必如实保留，不得在新机器把它包装成能力）
    facts["scripted_faults"] = {
        "source": "app/sw/scene_product.c (scene_node_off)",
        "note": "节点2 失联为写死时间窗 t∈[330,370)，中继12 损耗为 t∈[660,700)，由 cfg[11]（第2页'短时故障'）控制。"
                "这是按时间的剧本，不是故障自检测能力，UI 已加角标说明，禁止重新包装为'自愈'",
    }
    return facts


def pending_items() -> list:
    """本机（无 Vivado/SDK）无法完成、且已明确 layered 的待办。每条注明真正堵点。"""
    return [
        {
            "id": "P1",
            "needs": "sdk",
            "title": "重编 ELF：让板上固件与当前 sw/ 源码一致",
            "blocks_on": "Xilinx SDK 2018.3（不需要 Vivado）",
            "why": "app/sw 三个文件在 2026-10-25 改过，app/ready/swarm_app.elf 仍为 2026-10-23 产物；"
                   "PING 报告的 protocol 仍是 17、arm_build 仍是 20261021-edge1，"
                   "即板上跑的既不等于源码，也不等于 UI 声称的状态",
            "how": "xsct 执行 app/build_sdk.tcl（或按 HANDOFF/00 的菜单流程），用现成 system.hdf 生成 BSP 并编译",
            "evidence": "app/sw/main.c PING 行 + app/ready 产物时间戳对比"
        },
        {
            "id": "P2",
            "needs": "sdk",
            "title": "注入 TTL 自动到期（把'自愈'从叙事变成真实行为）",
            "blocks_on": "Xilinx SDK 2018.3（不需要 Vivado）",
            "why": "edge_apply 是 ARM 侧叠乘，加一个按帧递减的时长计数器即可到期自动撤除，"
                   "届时'无人值守自动解除'才第一次真正成立；在此之前 UI 必须保持现状不许宣称自愈",
            "how": "在注入状态里加 expire_at（按模型秒或批次数），每帧检查到期就自行清零 enabled，"
                   "同时新增下发字段让用户可以设定期望时长",
            "evidence": "app/sw/link_control.h edge_apply + network.c config_link"
        },
        {
            "id": "P3",
            "needs": "vivado",
            "title": "多径模型：2 抽头扩展到 4 抽头",
            "blocks_on": "Vivado 2018.3（真正需要 PL 重建）",
            "why": "two_path_link.sv 里 delayed0/delayed1 两级写死，抽头数与每级增益/时延寄存器成对存在",
            "how": "改 RTL 后走 check_core.tcl 打包 IP -> build_board.tcl 综合实现 -> 导出新 bit + hdf "
                   "-> 回到 SDK 更新 BSP 并重编 ELF（PL 变了，地址映射可能变）",
            "evidence": "app/rtl/two_path_link.sv delayed0/delayed1"
        },
        {
            "id": "P4",
            "needs": "sdk_then_vivado",
            "title": "衰落模型选择（Rayleigh / Rician）",
            "blocks_on": "分两档：块衰落可用 SDK 实现；逐符号衰落需要 Vivado",
            "why": "当前 PL 每帧锁存一次增益并保持不变。若按帧重采样瑞利/莱斯增益（ARM 侧每帧更新），"
                   "得到的是 block fading，属于真实且常见的近似；若要求每个符号独立衰落，"
                   "必须在 PL 内增加随机相位/幅度旋转",
            "how": "先以档案形式实现块衰落并在 UI 明示'逐帧（块）衰落'，不要把它说成逐符号",
            "evidence": "app/rtl/two_path_link.sv gain_hold 锁存 + app/sw/network.c 每帧调用 scene_link"
        },
        {
            "id": "P5",
            "needs": "sdk",
            "title": "载波频率区间对用户开放（不要等到 PL 重建）",
            "blocks_on": "SDK 重编即可（已放行的这一部分）",
            "why": "fc 只参与多普勒 CFO 计算，CFO 寄存器在 6000 MHz + 20 m/s 下仍有约 4 个数量级余量，"
                   "之前把它归入'必须重建 PL'属于过度保守的判断，应修正",
            "how": "随 P1 一起重编即可；Python 侧 carrier_mhz 区间已是 (200,6000)，"
                   "只需固件 cfg[13] 校验上限同步放开，UI 取消'协议18后开放'的免责声明",
            "evidence": "app/sw/scene_product.c:90 与 app/sw/network.c CFO 量化行"
        },
    ]


def build_snapshot() -> dict:
    git = head_commit()
    return {
        "schema": 1,
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "generated_on_host": os.environ.get("COMPUTERNAME", "unknown"),
        "project": {
            "name": "Zynq-7020 蜂群无人机基带级无线信道模拟仿真系统",
            "platform": "AMD Zynq xc7z020clg400-2（野火 EBF410020 V1R2 / EBF410021 V1.1）",
            "toolchain": "Vivado + SDK 2018.3 重新构建才需要；日常烧录用 OpenOCD/PCAP",
            "entrypoints": {
                "ui_and_experiments": "python portable_server.py --http 18878 --port COM5",
                "firmware_source": "app/sw（ARM C）",
                "pl_source": "app/rtl（SystemVerilog，26 个文件）",
                "vivado_scripts": "app/hw/*.tcl（check_core.tcl 打包 IP，build_board.tcl 综合实现）"
            }
        },
        "git": git,
        "artifacts": artifact_state(),
        "firmware_facts": scan_firmware_facts(),
        "pending": pending_items(),
        "red_lines": [
            "不得伪造实板数据、天气传感器、实时视频、协议标准或性能领先",
            "不得把时间窗写死的故障（scene_node_off / 660-700s 损耗）包装成'自检测/自愈'",
            "不得宣称硬件支持尚可酷、而未改 RTL 的 PL 能力",
            "每条'已支持'都必须能指到代码行；指不到就写'未做'"
        ]
    }


def export_rtl_package(make_zip: bool) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M")
    dest = ROOT / "build_handoff" / f"rtl_build_{stamp}"
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "rtl").mkdir(parents=True, exist_ok=True)
    (dest / "hw").mkdir(parents=True, exist_ok=True)

    copied = []
    for p in sorted(RTL.iterdir()):
        if p.is_file():
            shutil.copy2(p, dest / "rtl" / p.name)
            copied.append(f"rtl/{p.name}")
    for p in sorted(HW.glob("*.tcl")):
        shutil.copy2(p, dest / "hw" / p.name)
        copied.append(f"hw/{p.name}")
    # 上游 tcl 入口也需要（部分脚本按相对路径 source app/hw 下的文件）
    for name in ("build_sdk.tcl", "rebuild_firmware.tcl", "program_run.tcl"):
        p = APP / name
        if p.exists():
            shutil.copy2(p, dest / name)
            copied.append(name)

    readme = dest / "README_BUILD.txt"
    readme.write_text(
        "这是重建 PL 的最小文件集（不含 1.7GB 实验记录与 Python 运行时）。\n\n"
        "【在有 Vivado 2018.3 的机器上】\n"
        "  1) 打包 IP：\n"
        "       vivado -mode batch -source hw/check_core.tcl -tclargs <输出目录>\n"
        "  2) 建工程并综合实现（会生成 bitstream）：\n"
        "       vivado -mode batch -source hw/build_board.tcl -tclargs hw/board_config.wildfire7020.tcl "
        "<上一步ip_repo> <新输出目录>\n"
        "     注意：build_board.tcl 要求全新输出目录，且本机必须装有 xc7z020clg400-2 器件支持。\n"
        "  3) 实现通过后导出 .bit 与 .hdf（若 Python 侧涉及 PL 寄存器变化），\n"
        "     回到 SDK 侧更新 BSP 并重编 ELF，再拷回主工程 app/ready/ 覆盖旧产物。\n\n"
        "【不要在这些机器上做的事】\n"
        "  - 不要声称已经下板验证；脚本末尾明确写着 No hardware test performed，\n"
        "    未boarding 前不得改 HANDOFF/03 的验收结论。\n"
        "  - 时间/资源报告出来前不要断言'通过'，先看 finish_board.tcl 之后的时序与 DRC 报告。\n\n"
        "【原机器 jQuery】\n"
        f"  - 主工程源码 App(root) 位于 {ROOT}，如需要完整 UI 与实验流水请整体拷贝主工程。\n",
        encoding="utf-8",
    )

    manifest = {
        "purpose": "Vivado 侧重建 PL 的最小输入；不含 UI 与实验流水",
        "source_root": str(ROOT).replace("\\", "/"),
        "files": {name: sha256(dest / name) for name in copied},
        "vivado_required": "2018.3（2019+ 需核对 processing_system7 版本是否仍为 5.5）",
        "part": "xc7z020clg400-2",
    }
    (dest / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if make_zip:
        zip_path = dest.parent / f"rtl_build_{stamp}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for name in copied:
                z.write(dest / name, f"rtl_build_{stamp}/{name}")
            z.write(readme, f"rtl_build_{stamp}/README_BUILD.txt")
            z.write(dest / "MANIFEST.json", f"rtl_build_{stamp}/MANIFEST.json")
        print(f"已打包: {zip_path}")
    return dest


def main() -> int:
    HANDOFF.mkdir(exist_ok=True)
    snap = build_snapshot()
    out = HANDOFF / "context_snapshot.json"
    out.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=" * 60)
    print("接手上下文快照已生成:", out)
    print("=" * 60)
    art = snap["artifacts"]
    for key in ("sw_source", "elf", "bitstream"):
        a = art.get(key)
        if a:
            print(f"  {key:12s} {a['mtime']}  {a['size']:>9,d} B  {a['path']}")
    for w in art.get("_sync_warning", []):
        print("  [不同步] " + w)
    print(f"\n  git HEAD: {snap['git']['commit']}  (改动条目 {snap['git']['modified_entries']})")

    # 按显式 needs 字段分组，绝不用 blocks_on 里的关键词猜，
    # 否则"不需要 Vivado"这类措辞会被误判成"卡 Vivado"。
    groups: dict[str, list[str]] = {}
    for p in snap["pending"]:
        groups.setdefault(p.get("needs", "unknown"), []).append(p["id"])
    print(f"  待办共 {len(snap['pending'])} 项 —— 按真实依赖分组：")
    labels = {
        "sdk": "只需 SDK 重编（不必有 Vivado）",
        "vivado": "必须 Vivado 重建 PL",
        "sdk_then_vivado": "SDK 可先做一档，进阶需 Vivado",
        "unknown": "依赖未标注",
    }
    for need in ("sdk", "sdk_then_vivado", "vivado", "unknown"):
        if need in groups:
            print(f"    - {labels[need]:32s} : {', '.join(groups[need])}")

    if "--rtl" in sys.argv:
        dest = export_rtl_package("--zip" in sys.argv)
        print(f"\n最小 RTL 构建包: {dest}")
    else:
        print("\n提示: 加 --rtl 可另生成仅供 Vivado 机器使用的最小构建包")
    return 0


if __name__ == "__main__":
    sys.exit(main())
