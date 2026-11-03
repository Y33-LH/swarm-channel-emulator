# 面向蜂群自组网的无线信道模拟器

本工程面向教学实验与小规模组网方案验证。在一块 AMD Zynq-7020 上，16 个逻辑无人机节点经四组中继与地面站通信。ARM 根据编队运动、距离和场景更新信道，FPGA 分时执行逐跳 DBPSK 收发、时变多径叠加和加噪。上位机用同帧数据展示信道响应和均衡前后星座，支持网络态势、回放与对比。

| 路径 | 内容 |
|---|---|
| app/rtl、app/hw | FPGA 基带链、信道、板级约束、LCD 与 Vivado 构建入口 |
| app/sw、app/sdk_workspace_product | ARM 调度、链路协议、信道参数与 SDK 工程 |
| app/ui、app/tools | 上位机界面、串口服务与实验工具 |
| app/reference、app/tests、validation | 参考模型、仿真与验证脚本 |
| app/ready、app/release.json | 已构建硬件交接文件、固件与版本摘要 |

## 构建与复现

1. Windows 主机准备 Vivado 与 SDK 2018.3，包括 Zynq-7000 器件支持。根据实际安装路径修改 dev_settings.ps1。
2. 构建入口为 BUILD.cmd。脚本依赖 runtime/python/python.exe，发布的源码归档不含第三方 Python 运行环境、本地模型权重和推理引擎。离线演示使用配套完整运行包。
3. 查阅 app/README.md、app/docs/current_system_contract.txt 及根目录的《源码目录与工程入口》。SOURCE_SHA256.json 记录竞赛源码归档的原始文件摘要。

## 许可

团队原创代码采用 MIT 许可证。第三方 BSP、媒体、模型及工具依其各自许可，见 app/THIRD_PARTY_NOTICES.txt、licenses/、assistant/ 及相应源码头部。
