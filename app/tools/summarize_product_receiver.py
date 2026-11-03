"""Generate measurement figures from this product's actual receiver records."""
from pathlib import Path
import json,csv,sys,os
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,r'D:\digitalcircuit\tools\plot_deps')
os.environ['MPLCONFIGDIR']=r'D:\digitalcircuit\tools\matplotlib_cache'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
p=max((ROOT/'results').glob('receiver_study_*/acceptance.json'))
r=json.loads(p.read_text());rows=r['rows'];count=sum(x['measured']['attempts'] for x in rows)
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'axes.facecolor':'#102238','figure.facecolor':'#081421','text.color':'#dcecf7','axes.labelcolor':'#dcecf7','xtick.color':'#a8bed4','ytick.color':'#a8bed4','axes.edgecolor':'#3c5470','font.size':11})
fig,axes=plt.subplots(1,3,figsize=(17,5),layout='constrained')
panels=[('equal_complex_sample_snr','sample_snr_db','相同样点 SNR：编码能量更多'),('equal_information_ebn0','ebn0_db','相同保护信息位 Eb/N0'),('equal_total_frame_energy_per_payload_bit','payload_ebn0_db','相同总帧能量 / 载荷位（含前导）')]
for ax,(kind,key,title) in zip(axes,panels):
    for fec,color,label in [(0,'#ffbe6b','关闭纠错'),(1,'#51e1d0','完整纠错')]:
        rr=sorted([x for x in rows if x['config'].get('comparison')==kind and x['config']['fec']==fec],key=lambda x:x['config'][key])
        ax.plot([x['config'][key] for x in rr],[x['measured']['frame_delivery']*100 for x in rr],'o-',color=color,label=label,lw=2)
    ax.set_title(title,fontproperties=font,pad=18);ax.set_xlabel('dB');ax.set_ylabel('实际帧送达率 / %',fontproperties=font);ax.set_ylim(-5,105);ax.grid(alpha=.15);ax.legend(prop=font)
fig.suptitle(f'{count} 次实板收发 · 噪声点各 30 帧 · 连线仅连接已测点',fontproperties=font,fontsize=15)
fig.savefig(ROOT/'ui/receiver_study.png',dpi=120);plt.close(fig)
with (ROOT/'ui/receiver_study.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['case','fec','sigma','attempts','captured','delivered','pre_errors','pre_bits','post_errors','post_bits','clipped_iq_samples'])
    for x in rows:w.writerow([x['config']['name'],x['config']['fec'],x['config'].get('sigma',0)]+[x['measured'][k] for k in ('attempts','captured','crc_delivered','pre_errors','pre_bits','post_errors','post_bits','clipped_iq_samples')])
lines=[f'接收边界与公平对照：{count} 帧、{len(rows)} 个配置。来源 {p.relative_to(ROOT)}。',
       '范围分别测量：不能将单项极限直接拼成联合保证工作区。',
       '样点 SNR=A²/(2σ²)，A=8192，矩形脉冲每符号4样点。完整编码正文4752位，未编码正文784位；两者均另有542个前导符号。',
       '保护信息位 Eb/N0 比较使用784位（含CRC），不计前导能量。第三幅图按512个有效载荷位计算整帧总能量，包含前导。',
       '相同样点SNR下的送达改善，不等于相同载荷能量下的编码增益。此次未证明等能量编码优势；低能量编码点主要受同步捕获限制。',
       '未捕获时 BER 无样本，不能写作 BER=0；捕获失败保留在帧送达率分母。30/30也不证明零误码：独立同分布假设下零失败30次的一侧95%失败概率上界约9.5%。固定种子的工程测试不是统计认证。',
       '固定点削顶次数已单列；不是理想无限动态范围AWGN。采样钟偏差±200ppm仅有独立RTL波形证据，单板共用时钟不能证明双时钟实测。',
       '有限联合正向用例：频偏±5000Hz/衰减/相位；另有两径、相位、噪声、频偏组合。其余组合须实测，不承诺所有极端参数同时成立。','']
for x in rows:
    m=x['measured'];lines.append(f"{x['config']['name']}: 捕获 {m['captured']}/{m['attempts']}，送达 {m['crc_delivered']}/{m['attempts']}，译码后错误/位 {m['post_errors']}/{m['post_bits']}，削顶 {m['clipped_iq_samples']}")
(ROOT/'ui/receiver_study.txt').write_text('\n'.join(lines),encoding='utf-8')
(ROOT/'results/receiver_summary.json').write_text(json.dumps(dict(source=p.relative_to(ROOT).as_posix(),frames=count,configurations=len(rows),equal_energy_coding_gain_demonstrated=False,rows=rows),indent=2))
print('PRODUCT_RECEIVER_SUMMARY',count,len(rows))
