from pathlib import Path
import json,datetime,hashlib
R=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def latest(prefix):return sorted((R/'results').glob(prefix+'*/acceptance.json'))[-1]
audit_path=latest('specialty_audit_');audit=load(audit_path);assert audit['all_pass']
receiver_path=latest('receiver_study_');receiver=load(receiver_path)
capacity_path=latest('capacity_');capacity=load(capacity_path)
operation_path=latest('operation_comparison_');operation=load(operation_path)
extension_path=latest('modem_extension_');extension=load(extension_path)
mixed_path=latest('mixed_nodes_');mixed=load(mixed_path)
frame_count=sum(x['measured']['attempts'] for x in receiver['rows'])
failures=[dict(condition=x['config'],attempts=x['measured']['attempts'],captured=x['measured']['captured'],delivered=x['measured']['crc_delivered']) for x in receiver['rows'] if x['measured']['crc_delivered']<x['measured']['attempts']]
op=operation['rows']
summary=dict(updated=datetime.datetime.now().isoformat(),scope='Current unchanged bitstream and ARM image; explicitly bounded technical qualification',
 audit=str(audit_path.relative_to(R)),receiver=dict(configurations=len(receiver['rows']),frames=frame_count,failure_points=failures,source=str(receiver_path.relative_to(R))),
 capacity=dict(payload_bps=capacity['measured_sustainable_payload_bps'],scope=capacity['scope'],source=str(capacity_path.relative_to(R))),
 extension=dict(summary=extension['summary'],scope=extension['scope'],source=str(extension_path.relative_to(R))),
 topology=dict(hardware_nodes=mixed['hardware_nodes'],virtual_nodes=mixed['virtual_nodes'],source=str(mixed_path.relative_to(R)),scope='Fixed four-chain routes, shared PHY and isolated hardware endpoints; no dynamic route discovery'),
 operation=dict(source=str(operation_path.relative_to(R)),pending=[x['final']['pending'] for x in op],heartbeats=[x['final']['hb'] for x in op],video_bytes=[x['received_video_bytes'] for x in op],scope=operation['scope']),
 remaining=['Final complete product three-run freeze/rebuild qualification','Broader interaction review and complete presentation material','No calibrated standard channel or arbitrary user-modem upload claim'])
(R/'results/specialty_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
e=load(R/'docs/product_evidence.json');e['updated']=summary['updated'];e['accepted']=False;e['ui_runs']=[]
e['receiver']=dict(frames=frame_count,configurations=len(receiver['rows']),source=str(receiver_path.relative_to(R)),equal_energy_coding_gain_demonstrated=False,evidence_origin='Current physical-board rerun; finite sweep including failures')
e['capacity']=dict(summary['capacity'],evidence_origin='Current physical-board rerun')
e['action_specialty_audit']='results/specialty_summary.json'
(R/'docs/product_evidence.json').write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf-8')
resources=load(R.parent/'step23_network_intervention/results/resources.json')
for key,file in [('bit','system_wrapper.bit'),('elf','swarm_app.elf')]:assert resources['image_hashes'][key]==hashlib.sha256((R/'ready'/file).read_bytes()).hexdigest()
resources.update(ui_runtime_source=str(mixed_path.relative_to(R)),qualification_scope='Identical FPGA/ARM image hashes; prior static build resources retained, current board tests recheck stack guard and allocation failures')
(R/'results/resources.json').write_text(json.dumps(resources,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['2026-10-21 节点措施与技术专项复核','',
 '组合信道、算法扩展、混合节点、下行协议、场景一致性、受控业务对照、容量、接收范围：8项复核脚本全部完成并通过各自声明的检查。',
 f'接收范围：{len(receiver["rows"])}组条件、{frame_count}帧。下面保留不完全接收的测试点；完成扫描不等于全部范围无误码。',
 f'容量：{capacity["measured_sustainable_payload_bps"]:g} bit/s附加业务；'+capacity['scope'],
 f'受控措施：查询对照/暂停视频，待转发 {summary["operation"]["pending"]} 帧，收到视频 {summary["operation"]["video_bytes"]} 字节，心跳 {summary["operation"]["heartbeats"]} 条。',
 '业务措施能减少新负载与积压，但牺牲媒体交付速度；不得声称改善了物理传播或所有心跳时效。',
 '算法扩展是兼容DBPSK判决度量模块的软/硬判决替换，不是任意调制方案运行时上传。两种模式均通过25帧校验；这组结果不能证明某模式全面领先。',
 '宽带模型为8MHz采样、2Msymbol/s矩形DBPSK与二径复信道。频响来自应用系数，不冒充接收机信道估计或射频测量。',
 '固定四条多跳路径、2个FPGA硬件端点、14个ARM虚拟节点；支持链路扰动与恢复，不宣称自动路由。',
 '同采样信噪比与同信息/总帧能量的比较分开保存；当前仍不宣称已证明同总能量下的纠错优势。',
 '当前专项不替代最终版本连续三次整机验收，也不代表整件作品已冻结。','', '未全收齐的有限采样点：']
lines += [f'{x["condition"]["name"]}: 捕获{x["captured"]}/{x["attempts"]}，完整交付{x["delivered"]}/{x["attempts"]}' for x in failures]
(R/'专项复核与边界说明.txt').write_text('\n'.join(lines),encoding='utf-8-sig')
print(json.dumps({k:summary[k] for k in ('capacity','operation')},ensure_ascii=False));print('RECEIVER',len(receiver['rows']),frame_count,'failure_points',len(failures))
