# 蜂群通信实验室

登记作品名称：面向蜂群自组网的无线信道模拟器。

当前目录为 step27 冻结候选版。release.json 固定被测源码和固件；是否已通过工程验收，以 results/freeze_acceptance.json 中 pass_freeze 及匹配的 tested_manifest_sha256 为准，不能沿用历史版结论。源码清单不会在验收后改写。

单板数字基带实验平台。16 个逻辑无人机（其中 4 个中继）与 1 个地面站；每一跳的数据与 ACK 实际通过 FPGA。没有射频发射，也没有连接真实飞机。

## 开始使用

1. 给野火 Zynq-7020 开发板接外部电源，接 JTAG 与 USB TO UART。
2. 双击本目录 `launch.cmd`，打开 `http://127.0.0.1:8886/#causal`。固定桌面入口在本版验收通过后才切换。
3. 选择 CH340 对应的 COM 口。重新上电后点“上电后加载固件”；固件仍在运行则点“检查连接”。
4. 先选择任务：“交互验证”用于改变一条链路并观察业务影响；“单帧诊断”用于核对自定义正文与同帧接收；“完整场景”用于三环境、16节点、故障恢复及音视频。完整场景默认15模型分钟、高效显示。详细步骤见“新版界面_操作路线.txt”。
5. 第一页看应用信道参数、CIR/CFR与实际接收状态，第二页看地图、节点与业务。默认显示地面实际收到的位置；黄色“位置已过期”不是模型真值，也不代表已知飞机坠毁。节点选择器可以选择没有收到位置的节点。
6. 可暂停模型时钟，查看建议，确认发送查询或其他模拟指令，再继续。已排队不等于已执行；必须等到地面收到成功回报。失联时指令可能过期。
7. 实验结束后分别看“最终送达”和“按时送达”。只播放完整重组、逐字节校验的音视频。
8. 第三页“回放与对比”可载入历史、90秒回放、比较条件及导出摘要/CSV/证据。回放禁止硬件控制，不能当作计算加速。

所有实验、导出、可选模型都位于 D 盘。软件没有自动联网地图或在线模型依赖。实际 COM 号以设备管理器为准。

## 环境与板型

- 实测板卡：野火 xc7z020clg400-2；PS/DDR 初始化只适用于已核对的此板配置。不能直接向不同 PYNQ 板或不同 DDR 配置下载同一文件。
- Vivado / SDK 2018.3：`D:\Xilinx\Vivado\2018.3` 与 `D:\Xilinx\SDK\2018.3`。
- Python：`D:\miniconda\python.exe`，使用 numpy、opencv-python；串口依赖已放在 `tools/python_deps`。
- 浏览器：Chrome 或 Edge。默认本地服务端口 8878，UART 230400 / 8N1。
- 本次 Python、NumPy、OpenCV、matplotlib、pySerial 及浏览器测试框架的实测版本记录在 `docs/environment_versions.json`；浏览器自动化测试依赖 Node/Playwright，日常演示不需要运行这些测试工具。
- 正常入口会启动已安装的本地模型；`start.ps1 -RulesOnly` 可选择只用规则。模型启动失败时界面如实提示，规则建议仍可用。此模型仅选择已有证据，不输出未经校验的自由判断，必须经用户确认才能发送控制命令。
- 不需要 PetaLinux、MATLAB、ModelSim 或新下载 Vitis 才能运行本版。RTL 使用 Vivado 自带 XSim 测试。

## 三层分工

| 层 | 实际职责 |
|---|---|
| FPGA / PL | 独立硬件节点9/13的业务产生、缓存、命令执行、ACK和重传；扰码、交织、卷积码、Turbo、DBPSK、复数二径/噪声、PN捕获、符号定时、频偏估计补偿、DFE均衡、译码、CRC、接收字节及计数 |
| ARM / PS | 其余14个虚拟节点和地面站；场景与连续轨迹、定时业务、固定路由、TDMA、有限重传/缓存、去重、下行指令及回执、串口协议 |
| PC | 参数校验、显控、地图、证据保存/重放/对比、规则建议、可选模型检索 |

一套 PL 核心时分复用；空空、空地两类信道，32 个有向链路上下文，不宣称两个并行核。采样模型 8 MHz、DBPSK 2 Msymbol/s，不是持续串口或射频吞吐。

## 工程目录和复现

| 本工程 | 指南推荐目录含义 |
|---|---|
| rtl / sw / tools / ui | src：RTL、ARM、PC、网页 |
| tests / reference | sim：独立参考、RTL、实板和浏览器测试 |
| hw / build_release.ps1 / build_sdk.tcl | build：完整构建入口 |
| ready / hw/board_config.wildfire7020.tcl | board：匹配固件、初始化和板卡配置 |
| results / media / configs | data：原始测量、媒体和配置 |
| skill | 可复用工程方法和 AI 协作更正记录 |
| docs | 接口、指标、资源、证据索引与未来报告构思 |

`release.json` 记录源文件及匹配 BIT / ELF / 初始化脚本的 SHA-256；运行前自检。重新构建会将版本标为开发状态，不沿用旧验收。

开发者重建：在项目目录使用 `powershell -ExecutionPolicy Bypass -File build_release.ps1`。须有上述 AMD 工具和 Zynq-7000 器件支持。此过程从 RTL 打包 IP、构建 PS+PL、检查时序、构建 ARM，再生成开发清单；产生文件不等于已经通过板卡验收。

主要验证入口：`simulate.ps1`、`test_phy.ps1`、`test_fec.ps1`、`tests/product_scene_acceptance.py`、`tests/acceptance.py`、`tests/product_control_acceptance.py`、`tests/receiver_study.py`、`tests/product_scenarios.py`、`tests/product_ui_hardware.cjs`。实板测试之间不得并发使用 COM 口。详细结果见 `docs/product_evidence.json` 与 `docs/progress.json`。

完整当前版本验收顺序：仿真及构建 → `tools/qualify_delivery.py`（包含混合节点、缺ACK重试、噪声、接收边界、容量、业务操作对照）→ `tools/summarize_product_receiver.py` → `tools/finalize_delivery.py --prepare` → 更新开发清单并保存至 `results/freeze_input_manifest.json` → 界面/AI实板测试及三次整机运行 → `tools/finalize_delivery.py --accept`。最后一步会核对同版哈希和各项门禁；失败不能改为人工填“通过”。

## 使用范围与解释

- 7 种独立环境、8 种天气、9 种编队，加原三环境演示。天气为受控参数组，未进行气象或实际地形标定。
- 几何参数只在开始前更改；X形基准锁定几何。运行中只有明确的指令可以改变模拟状态。
- 默认900模型秒的目标是全流程不超过120电脑秒、最终送达率不低于99%；不推广为所有恶劣配置均99%。必须同时看及时送达和最大模型时延。
- 有效容量来自固定负载扫描，不是香农容量。相同采样 SNR 对比不能单独证明编码增益；当前同总帧能量对照未证明编码增益。
- 音频约0.83秒、视频2秒，为完整文件传输，不是实时摄像头直播。
- 本版采用用户确认的板内方案：PL节点9/13 + 14个ARM虚拟节点。端点的独立生成、隔离复位、真实收发和下行命令均须通过本版实板验收；不宣称外部无人机或第二块板已接入。
- 自动发现、动态选路、自由航点、射线追踪、真实飞行不是本版已交付内容。

## 常见恢复

- 找不到串口：检查 USB TO UART，关闭其他串口助手，重新选择端口。
- 固件版本不符或重新上电：点击加载固件，不能混用旧 ELF 和新 BIT。
- 串口异常：先中止或等待任务退出，再重新检查连接。总线彻底失去响应时才需要重新上电后加载。
- 配置越界：界面说明越界原因；减少间距、移动中心或改选编队。不要绕过校验。
- 信道太差：保留失败记录，与晴天/更短距离/理想模式对照。系统不会从发送原文补回缺失数据。
- 性能超时：关闭独立重负载程序，采用高效遥测。历史回放不是性能达标依据。

正式报告与视频按用户安排后续制作。开发过程的报告思路保存在 `docs/report_concepts.txt`，原始证据随功能推进更新。公开仓库发布、报名手续和现场能力考核不由本机程序代替。
