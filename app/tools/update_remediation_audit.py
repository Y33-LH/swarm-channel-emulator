"""Reconcile the dated 54-item audit with current, scoped evidence.

Never equate a scoped experiment or a declared boundary with whole-product
acceptance. Preserve the initial audit and explicitly retain open items.
"""
from pathlib import Path
import json,datetime,hashlib
ROOT=Path(__file__).resolve().parents[1]
AUDIT=Path('D:/digitalcircuit/audit_20261101')
p=AUDIT/'remediation_status.json';d=json.loads(p.read_text(encoding='utf-8-sig'))
def latest(pattern):
 ps=list(ROOT.glob(pattern));assert ps,pattern
 return max(ps,key=lambda p:p.stat().st_mtime).relative_to(ROOT).as_posix()
board=latest('results/board_suite_*/report.json')
multi=latest('results/multitap_board_*/acceptance.json')
terrain=latest('results/terrain_headroom_board_*/acceptance.json')
story=latest('results/current_story_*/acceptance.json')
stable=latest('results/current_network_stability_*/acceptance.json')
joint=latest('results/joint_receiver_*/study.json')
fair=latest('results/fair_payload_energy_*/acceptance.json')
contract='docs/current_system_contract.txt'
# State: V = verified within described scope; B = explicit capability boundary;
# P = still pending. A capability boundary is not a test or a waiver.
rows={
1:('V','当前 RTL/SDK 源码、镜像摘要、板上 PING 和重新干净构建已绑定。',[board,'results/sdk_clean_continuous1/acceptance.json','docs/product_build.json']),
2:('V','当前固件三次900秒和持续运行无遥测解析失败；主机串口半帧中断、禁止错帧重试、重开后32包专项已通过，未进行物理拔线。',[stable,story,latest('results/serial_interrupt_*/acceptance.json')]),
3:('V','汇总不再把脚本 pass 当整机通过；旧冻结脚本拒绝误签，accepted 仍为 false。',['tools/current_evidence.py','tools/finalize_delivery.py','tools/finalize_freeze.py']),
4:('V','当前合同、运行说明与交接说明已更新；官方入口清单完整性检查通过，历史归档不覆盖当前版本。',[contract,'results/final_ui_20261101/launcher_check.log']),
5:('V','三环境、天气切换不再暗改噪声；UI 34→24dB 对应实际 sigma 116→365。',[multi,story]),
6:('V','归一参考功率无量纲，不称1W；B/Fs/Rs及三种能量比较口径已明确。',[contract,'docs/receiver_energy_definitions.json',fair]),
7:('V','32项散射的Rayleigh/Rician统计参考、ARM读回、FPGA波形与动态余量分别验证；并非标准认证模型。',['results/channel_model_statistics.json',multi,terrain]),
8:('V','1–8独立抽头；1/3/8抽头实板连续采样与独立定点oracle逐样本一致。',[multi]),
9:('V','自主信道直接使用用户抽头及公共参数，不继承场景信道；场景仅继续驱动运动与业务。',[multi,'tools/channel_config.py','ui/channel-controls.js']),
10:('V','载波参与场景传播和几何多普勒；自主模式频偏直接设定，语义明确。',['results/product_scene_acceptance.json',multi]),
11:('V','几何径向多普勒、振荡器/散射偏移、接收估计CFO分开；不以fc*v/c冒充实测。',['ui/instrument.js',multi]),
12:('V','当前几何模型ARM/Python对照、DEM跨语言616点已核对。',['results/product_scene_acceptance.json','results/terrain_ui_reference.json']),
13:('V','亚公里距离损耗连续变化，不再把1km以下全部钳平；有限距离点实板读回。',['results/product_scene_acceptance.json',terrain]),
14:('V','1–6GHz雨衰采用P.838-3；雾雪为明确的经验参数，未称实测气象。',['results/channel_model_statistics.json',contract]),
15:('V','同一程序DEM参与63点剖面主障碍绕射；非真实地形、建筑射线追踪。',[terrain,'results/terrain_headroom_reference.json','results/terrain_ui_reference.json']),
16:('V','场景/高度映射路径数、等效损耗、散射和几何；逐路径反射阶仅为等效标签。',['ui/channel-controls.js','sw/scene_product.c',contract]),
17:('V','量化AWGN参考分布、RTL样本和当前实板噪声接收已验证。',['results/channel_reference_20261101_042456/acceptance.json',latest('results/noise_acceptance_*/acceptance.json')]),
18:('V','绝对模型时间+独立链路种子，帧内相位/幅度局部一阶演化；误差和削顶有记录。',['results/channel_model_statistics.json',multi,terrain]),
19:('V','参数范围、整数时延量化、共同缩放余量及联合接收失败边界均保留。',[contract,terrain,joint]),
20:('B','2类传播、32有向上下文、1共享核心；当前2个PL端点+14ARM节点，非MIMO。',[contract]),
21:('V','第三完整端点同规格构建在布局阶段失败：剩余6523 Slice，未放置逻辑需7210；保留2端点。此候选失败不能证明所有架构全局最优。',['results/endpoint_count_study_20261101/study.json','results/current_hierarchy_utilization.rpt']),
22:('V','100ms=20×5ms模型预算；波形/PL未超限，但ARM存在>5ms服务，不能宣称严格实时。',[stable,'sw/network.c','ui/instrument.js']),
23:('V','ACK丢失、截止时间、负载竞争、指令幂等、重传和队列边界专项已测；未覆盖任意拓扑。',[board,latest('results/ack_deadline_*/acceptance.json')]),
24:('V','自定义业务帧/CRC16/逐跳ACK+UART CRC32重放+AXI4-Lite已明确；未接MAVLink/WiFi路由栈。',[contract,'docs/registers.json']),
25:('V','固定四条四跳、全纠错、理想信道负载试验测得额外净荷12288bit/s；不是RF或通用网络容量。',[latest('results/capacity_*/acceptance.json')]),
26:('B','TX/RX仅选择真实32条有向边，自动约束合法对端；不以观察下拉框声称任意路由创建。',['ui/params-rail.js',contract]),
27:('B','实际开放兼容DBPSK判决模块，并有软/硬判决实板比较；任意调制波形导入尚未实现。',[latest('results/modem_extension_*/acceptance.json'),contract]),
28:('V','36组联合信道18290次DATA；强长多径/深Rayleigh确有低成功率，界限如实列明。',[joint]),
29:('V','完整纠错流程；200对同净荷/总帧能量/种子且无削顶，156/200对200/200；仅此工作点收益。',[fair,board]),
30:('V','完整RX逐字节匹配，坏帧不交付；未收齐媒体不可播放，缺片不由TX补齐。',[story,latest('results/export_integrity_*/acceptance.json')]),
31:('V','图表绑定run/link/generation/config，实读抽头、同帧连续采样和符号一起核验。',[latest('results/coherent_board_*/report.json'),story,'tools/observation_contract.py']),
32:('V','眼图来自128个连续实收采样，4点/符号；不再插值离散判决符号造眼图。',[multi,'ui/instrument.js']),
33:('V','历史研究与实时样本能量域分开；无共同口径不能叠加成同一性能曲线。',['ui/observation.js','ui/study-live.js','docs/receiver_energy_definitions.json']),
34:('V','零误码使用非零Wilson上界并给出有效样本数；相关误码时只称二项近似。',['ui/observation.js','ui/params-rail.js']),
35:('V','跨记录/链路缓存按上下文清除；历史只读，不能发送新指令或将旧IQ套用新配置。',['tests/test_observation_contract.py','tests/test_workflow.py',story]),
36:('V','相干带宽标为经验粗估；相干时间不由单一CFO倒推；不将Shannon上界当实测容量。',['ui/instrument.js',contract]),
37:('V','按真实帧generation去重，不以浏览器刷新计观测次数。',['ui/observation.js',story]),
38:('V','连续航标为标明的模型轨迹；实收心跳独立显示，曲线仅连接实测帧；稳定曲线不强行抖动。',[story,'ui/instrument.js']),
39:('V','三次最终送达100%，按时99.6078%；最大40.218秒延迟明确保留，不混称全部及时。',[stable]),
40:('V','持续重复发送独立编号校准音视频，各段多跳实收；非现场音视频，失败段保留。',[story,'sw/network.c']),
41:('V','实际5→1分片/秒命令地面回执与后续生成速率分离；效果由实收窗口确认。',[story,'tools/action_observation.py']),
42:('V','注入动作、观测失败和恢复三个事件分开；71秒人为劣化后手动恢复，实收ACK/HB证实。',[story]),
43:('V','当前链路/时间/节点指令与效果进入AI事实；历史不借未来数据，过期提议重新核验后确认。',['tests/test_workflow.py','tests/test_assistant_live_context.py',story,'tools/assistant_workflow_facts.py']),
44:('V','当前配置开始→观察→人为变差→处置→恢复→保存重算；无自动切页/预设结局或20秒限时。',[story,'ui/demo-guide.js']),
45:('V','三页在1920×1080与1280×720核验无整页溢出；首页8图可见，细节弹窗放大，地图占据中央，回放比较与证据分屏。',['results/final_ui_20261101/receipt.json']),
46:('V','左侧B/fc/v/SNR、场景与衰落；自主抽头有界开放，编辑值与本轮已应用值明确分开。',['ui/channel-controls.js','ui/instrument-desktop.js',story]),
47:('V','八图4×2：左半PDP/CFR/幅度时序/链路质量，右半前后星座/真实眼图/16路星座墙。星座墙只放已采样链路，标注非同步快照。',['ui/instrument-desktop.css','ui/instrument.js','results/final_ui_20261101/receipt.json']),
48:('V','首页左下俯视投影/拓扑、三蜜蜂标志、统一正文已在两分辨率截图核验；1280图表较紧凑，可打开图表放大。',['results/final_ui_20261101/receipt.json']),
49:('V','主流程与非法SNR阻断已核验；修复结束后速度锁住、历史返回/启动时所选观测链路错位。175秒持续运行后再开始、修改草稿、明确应用另建记录通过。不是对每种输入组合的穷尽保证。',[story,'results/ui_pause_parameter_20261101.json','results/final_ui_20261101/receipt.json']),
50:('V','刷新恢复当前链路/配置，跨页显示同记录；草稿2500MHz/14m/s不改写原2400MHz/12m/s结果，明确应用后新记录实读生效。历史倒回不显示未来文件/回执。',['results/final_ui_20261101/receipt.json']),
51:('V','历史只读与实际重算分开；最新手动故事实板复算193/193快照、全部完整与不完整媒体一致，0差异；墙钟耗时与硬件绝对计数不作为确定性比较对象。',['results/network_20261101_064541_1f90e6/acceptance.json','tools/network_reproduction.py']),
52:('V','有当前镜像对照、均衡/判决/纠错与缺点记录；不声称领先商用仪器或全环境99%。',[fair,joint,board]),
53:('V','当前镜像绑定LUT/DSP/BRAM/时序、ARM静态内存、栈保守界与堆峰值；不是整机DDR测量。',['results/resources.json',stable]),
54:('V','当前镜像三次整机、连续交互主线、重新上板计算、串口会话恢复、官方入口清单与最终UI核验完成。此开发版的限定范围验收不等于竞赛最终签收；能力边界和失败点继续保留。',[stable,'docs/product_evidence.json','results/final_ui_20261101/receipt.json','results/final_ui_20261101/launcher_check.log'])}
assert set(rows)==set(range(1,55))
for item in d['items']:
 state,note,paths=rows[item['id']]
 for path in paths:assert (ROOT/path).is_file(),path
 item.update(status={'V':'verified_with_scope','B':'implemented_with_explicit_boundary','P':'pending'}[state],current_finding=note,evidence=paths)
d.update(last_update=datetime.datetime.now().isoformat(),accepted=False,
 current_phase='Current-image scoped development qualification reconciled; UI workflows and official entry checked; third-endpoint placement failure retained; final competition submission is not signed',
 status_semantics='verified_with_scope applies only to the attached checks; boundary is not a waiver of future requirements; pending remains unfinished')
d['loading_fallback_fix']=dict(state='current_bit_derived_pcap_verified',evidence='ready/pcap_source.json',detail='Derived from current matching bitstream; not a legacy fallback image')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['2026-11-01 当前整改进度（不是整机最终验收）','根目录：'+str(ROOT),'原始审查保留；以下结论仅对应当前000d0005 / 20261101-continuous1。','']
for i in d['items']:
 lines.extend([f"{i['id']:02d}. [{i['status']}] {i['title']}",i['current_finding'],'依据：'+'；'.join(i['evidence']),''])
(AUDIT/'当前整改进展与剩余项.txt').write_text('\n'.join(lines),encoding='utf-8')
print('AUDIT_UPDATED', {s:sum(i['status']==s for i in d['items']) for s in sorted({i['status'] for i in d['items']})})
