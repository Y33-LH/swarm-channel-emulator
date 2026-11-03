import json,csv,math,sys,os
from pathlib import Path
sys.path.insert(0,r'D:\digitalcircuit\tools\plot_deps')
os.environ['MPLCONFIGDIR']=r'D:\digitalcircuit\tools\matplotlib_cache'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
ROOT=Path(__file__).resolve().parents[1]
if json.loads((ROOT/'release.json').read_text())['version']=='000d0003':
 raise SystemExit('Use summarize_product_receiver.py for the current release; this legacy summary includes historical measurements.')
p=max((ROOT/'results').glob('receiver_study_*/acceptance.json'))
r=json.loads(p.read_text());rows=r['rows'];count=sum(x['measured']['attempts'] for x in rows)
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'axes.facecolor':'#0c1c31','figure.facecolor':'#071426','text.color':'#d6e8ff','axes.labelcolor':'#d6e8ff','xtick.color':'#a8bed4','ytick.color':'#a8bed4','axes.edgecolor':'#3c5470','font.size':12})
fig,axes=plt.subplots(1,2,figsize=(15.5,5.5),layout='constrained')
for ax,kind,key,title in [(axes[0],'equal_complex_sample_snr','sample_snr_db','相同样点信噪比（编码帧耗时、能量更多）'),(axes[1],'equal_information_ebn0','ebn0_db','相同信息位能量 Eb/N0（含捕获失败）')]:
 for fec,color,label in [(0,'#ffc86b','关闭纠错'),(1,'#49e3e1','完整纠错')]:
  rr=sorted([x for x in rows if x['config'].get('comparison')==kind and x['config']['fec']==fec],key=lambda x:x['config'][key])
  xx=[x['config'][key] for x in rr];yy=[x['measured']['frame_delivery']*100 for x in rr]
  ax.plot(xx,yy,'o-',color=color,label=label,linewidth=2,markersize=7)
  for x,y,row in zip(xx,yy,rr):
   if y not in (0,100):ax.annotate(f"{row['measured']['crc_delivered']}/30",(x,y),xytext=(8,-18),textcoords='offset points',color=color)
 ax.set_title(title,fontproperties=font,pad=18);ax.set_xlabel('dB');ax.set_ylabel('帧送达率 / %',fontproperties=font);ax.set_ylim(-5,105);ax.grid(alpha=.15);ax.legend(prop=font)
fig.suptitle(f'{count} 帧真实 FPGA 实测 · 每个噪声点 30 帧；连线只连接已测点',fontproperties=font,fontsize=16)
fig.savefig(ROOT/'ui/receiver_study.png',dpi=120);plt.close(fig)
csvpath=ROOT/'docs/接收性能实测数据.csv'
with csvpath.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['case','fec','sigma','attempts','captured','delivered','pre_errors','pre_bits','post_errors','post_bits','clipped_iq_samples'])
 for x in rows:w.writerow([x['config']['name'],x['config']['fec'],x['config'].get('sigma',0)]+[x['measured'][k] for k in ('attempts','captured','crc_delivered','pre_errors','pre_bits','post_errors','post_bits','clipped_iq_samples')])
lines=['# 接收边界与公平纠错对照','',f'来源：{p.relative_to(ROOT)}。共{count}次实际FPGA收发，35组配置。非软件替代接收。','',
'- 在各自测试条件下：±7000 Hz频偏、0/128/256/512样点时延均8/8通过；增益0.1、噪声σ=200条件8/8通过，增益0.05条件0/8捕获。不能把这些独立边界同时组合为保证工作区。',
'- 相同样点SNR=6 dB，关闭纠错26/30送达，完整纠错30/30。编码正文4752比特、未编码784比特，编码帧占用更多时间和能量。',
'- 相同信息位Eb/N0=16 dB，关闭纠错30/30，完整纠错0/30，失败发生于PN捕获；20 dB两者均30/30。现版不能宣称在相同信息位能量下已有编码增益，强噪声捕获仍是明确限制。',
'- 0/30送达不等于BER=1；未捕获帧没有有效正文BER，必须用帧失败率表示。30/30也不证明误码率为零：在独立同分布假设下，零失败30次对应的一侧95%帧失败率上界约9.50%。本次固定种子有限试验本身不是统计认证。',
'- 样点SNR定义为A²/(2σ²)，A=8192。矩形脉冲每符号4个复数样点；信息位Eb/N0对照按码率1或784/4752折算噪声。542符号前导不计入信息位能量，但实际发送并承受相同噪声。码率变低时同步也更困难。',
'- 固定位宽有饱和：Eb/N0=8/12 dB的完整纠错点分别出现13439/156次I/Q样点削顶，保留并单列，不把它们解释成理想浮点AWGN曲线。','',
'|配置|尝试|捕获|CRC送达|纠错前错误/位|正文错误/位|','|---|---:|---:|---:|---:|---:|']
for x in rows:
 m=x['measured'];lines.append(f"|{x['config']['name']}|{m['attempts']}|{m['captured']}|{m['crc_delivered']}|{m['pre_errors']}/{m['pre_bits']}|{m['post_errors']}/{m['post_bits']}|")
lines+=['','接收时钟偏差±200 ppm的证据来自独立输入波形RTL仿真；板上共用时钟的闭环不冒充两台独立时钟测试。','场景参数采用教学演示模型，未经过实飞标定，不作射频覆盖范围或适航结论。']
(ROOT/'docs/接收范围与公平对照.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(ROOT/'results/receiver_summary.json').write_text(json.dumps(dict(source=str(p.relative_to(ROOT)),frames=count,configurations=len(rows),capture_limit_disclosed=True,equal_energy_coding_gain_demonstrated=False),indent=2))
print('RECEIVER_SUMMARY_WRITTEN',count)
