# 本版工具入口

日常运行用上级 `launch.cmd` / `start.ps1`。本版端口8878、PL 000d0003、ARM协议17。

- `server.py`：单串口所有者、任务管理、实验及UI接口。
- `product_config.py`：唯一参数字段和范围；`product_metrics.py`：指标窗口及实验可比性。
- `product_advice.py`：依据实际接收证据生成建议；`product_assistant.py`：可选模型只选择已有证据。
- `endpoint_gateway.py`：保留的外接端点协议网关。当前验收使用PL内独立节点9/13；第二板物理接入未验收。
- `rebuild_product.ps1`：重建ARM并产生开发清单，可加 `-Program` 加载。
- `development_manifest.py`：检查软件与编译源码对应，生成**未验收**的开发清单。
- `adopt_product_build.py`：验证已构建RTL、PS初始化、资源与时序。
- `summarize_product_receiver.py`：从当前接收测试记录生成图表与配置/帧数统计。
- `qualify_delivery.py`：顺序运行实板测试，保存与固件、测试脚本、原始证据绑定的收据。
- `finalize_delivery.py`：要求三个不同UI实板实验、精确固件和运行源码对应后，冻结单板工程；不会把双板和人工试用标为已完成。旧finalize脚本不适用于本版。
- `start_assistant.ps1`：启动可选本地证据选择模型；加 `-Stop` 只关闭本任务自己的模型进程。

最终开发验收索引为 `results/product_acceptance.json`，阶段状态为 `docs/progress.json`。
本目录未被运行入口调用的旧研究辅助脚本不是安装步骤。旧界面测试已放入 `reference/legacy_step18/tests`，不能用于宣称新版本通过。
