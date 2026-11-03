"""Portable, local-only launch and setup. No system Python/PATH dependencies."""
import argparse,ctypes,hashlib,json,os,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
APP=ROOT/'app'
sys.path[:0]=[str(APP/'tools/python_deps'),str(APP/'tools')]
import serial
from serial.tools import list_ports
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def config():
    d=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig'))
    for k in ('http_port','ai_port'):
        if type(d[k])!=int or not 1024<=d[k]<=65535:raise ValueError('端口必须为1024–65535的整数')
    if d['http_port']==d['ai_port']:raise ValueError('网页端口和AI端口不能相同')
    return d
def request(port,path='/api/info',body=None,timeout=3):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json'})
    with OPENER.open(req,timeout=timeout) as r:return json.load(r)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def check():
    manifest=json.loads((ROOT/'PACKAGE_SHA256.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        p=ROOT/row['path']
        if not p.is_file() or sha(p)!=row['sha256']:raise RuntimeError('文件不完整或被修改：'+row['path'])
    import numpy,cv2,ssl,hashlib,zlib,ctypes as ct
    cap=cv2.VideoCapture(str(APP/'media/source_video.webm'));frames=0
    while cap.read()[0]:frames+=1
    cap.release()
    if frames!=20:raise RuntimeError('视频运行库不能正确解码内置样本')
    d=config();ports=[dict(port=p.device,description=p.description) for p in list_ports.comports()]
    result=dict(files_verified=len(manifest['files']),python=sys.version,numpy=numpy.__version__,opencv=cv2.__version__,video_frames=frames,ports=ports,xsct=d['xsct'],sdk_exists=Path(d['xsct']).is_file() if d['xsct'] else False,board_profile=d['board_profile'],runtime=sys.executable)
    (ROOT/'logs').mkdir(exist_ok=True);write(ROOT/'logs/preflight.json',result)
    print(f'文件校验通过：{len(manifest["files"])}项；Python/串口/图像运行库正常。')
    for p in ports:print(f'  {p["port"]}: {p["description"]}')
    print('SDK：'+(d['xsct'] if Path(d['xsct']).is_file() else '无需SDK · 使用随包OpenOCD（JTAG A接口需匹配驱动）'))
    print('板型：'+d['board_profile'])
    return result
def sdk_candidates():
    found=[]
    for drive in ('C:','D:','E:','F:'):
        for sub in ('Xilinx/SDK/2018.3/bin/xsct.bat','AMD/SDK/2018.3/bin/xsct.bat'):
            p=Path(drive+'/')/sub
            if p.is_file():found.append(str(p))
    return found
def bundled_loader():
    return ROOT/'app/openocd/openocd/xpack-openocd-0.12.0-7/bin/openocd.exe'

def setup():
    d=config();ports=list(list_ports.comports())
    for p in ports:print(p.device,p.description)
    v=input('USB TO UART 对应的 COM 号（如 COM4）：').strip().upper()
    import re
    if not re.fullmatch(r'COM\d+',v):raise ValueError('串口格式不正确')
    d['port']=v
    candidates=sdk_candidates()
    suggestion=d['xsct'] if Path(d.get('xsct','')).is_file() else ''
    print('无需安装SDK：直接回车使用随包OpenOCD。已有SDK也可填xsct.bat完整路径。')
    v=input('路径（回车保留 '+(suggestion or '未设置')+'）：').strip().strip('"') or suggestion
    if v and (not Path(v).is_file() or Path(v).name.lower()!='xsct.bat'):raise ValueError('未找到 xsct.bat')
    if not v and not bundled_loader().is_file():raise ValueError('随包加载工具缺失')
    d['xsct']=str(Path(v).resolve()) if v else ''
    print('固件只适配已核对的野火 Zynq-7020 / xc7z020clg400-2 板与原 DDR/PS 接法。')
    print('同一块原板转移电脑可直接选择。PYNQ或其他7020板不能只按芯片型号选择。')
    d['board_profile']='wildfire7020' if input('确认是上述匹配板卡，输入 YES：').strip().upper()=='YES' else 'unconfirmed'
    write(ROOT/'config.json',d);print('配置已保存。若服务已运行，请菜单4停止后重新启动。')
def services():
    try:return json.loads((ROOT/'services.json').read_text())
    except (FileNotFoundError,ValueError):return {}
def proc_path(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
    k.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x1000,False,int(pid))
    if not h:return None
    try:
        b=ctypes.create_unicode_buffer(32768);n=ctypes.c_ulong(len(b))
        return Path(b.value).resolve() if k.QueryFullProcessImageNameW(h,0,b,ctypes.byref(n)) else None
    finally:k.CloseHandle(h)
def spawn(name,exe,args,env):
    (ROOT/'logs').mkdir(exist_ok=True)
    with (ROOT/'logs'/f'{name}_stdout.log').open('ab') as out,(ROOT/'logs'/f'{name}_stderr.log').open('ab') as err:
        p=subprocess.Popen([str(exe),*args],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    d=services();d[name]=dict(pid=p.pid,exe=str(Path(exe).resolve()));write(ROOT/'services.json',d);return p
def ai(d):
    if not d['ai_enabled']:return
    s=services().get('assistant');exe=ROOT/'assistant/runtime/llama-server.exe'
    try:
        request(d['ai_port'],'/v1/models')
        if s and proc_path(s['pid'])==exe.resolve():print('本包AI已运行');return
        raise RuntimeError('AI端口已被其他程序占用，请调整 config.json 中的 ai_port')
    except (OSError,ValueError):pass
    env=os.environ.copy()
    model=ROOT/'assistant/Qwen3-0.6B-Q8_0.gguf'
    p=spawn('assistant',exe,['-m',str(model),'--alias','Swarm-Qwen3-0.6B-Q8','--host','127.0.0.1','--port',str(d['ai_port']),'--threads','4','--threads-batch','4','--ctx-size','8192','--parallel','1','--reasoning','off','--no-webui'],env)
    deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        if p.poll() is not None:raise RuntimeError('本地AI启动失败，请看 logs/assistant_stderr.log')
        try:
            if request(d['ai_port'],'/v1/models').get('data'):print('本包本地AI已就绪');return
        except (OSError,ValueError):pass
        time.sleep(.4)
    raise RuntimeError('本地AI尚未就绪，请看日志；主程序仍可用规则模式')
def start(no_browser=False):
    d=config();check()
    if d['board_profile']!='wildfire7020' or not d['port']:raise RuntimeError('请先用菜单2配置串口并确认板卡')
    if not Path(d['xsct']).is_file() and not bundled_loader().is_file():raise RuntimeError('缺少随包加载工具；也可配置已有SDK')
    already=False
    try:
        info=request(d['http_port'])
        if Path(info.get('root','')).resolve()!=APP.resolve():raise RuntimeError('网页端口被其他程序占用，请调整config.json')
        already=True
    except (OSError,ValueError):pass
    if not already:
        try:ai(d)
        except Exception as e:print('AI提示：'+str(e)+'。UI将如实显示规则模式。')
        env=os.environ.copy();env.update(SWARM_XSCT=d['xsct'] if Path(d['xsct']).is_file() else '',SWARM_BOARD_PROFILE=d['board_profile'],SWARM_ASSISTANT_URL=f'http://127.0.0.1:{d["ai_port"]}',PYTHONUTF8='1')
        p=spawn('web',sys.executable,['-X','utf8','-B',str(ROOT/'portable_server.py'),'--http',str(d['http_port']),'--port',d['port']],env)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if p.poll() is not None:raise RuntimeError('网页服务退出，请看logs/web_stderr.log')
            try:
                if Path(request(d['http_port']).get('root','')).resolve()==APP.resolve():break
            except (OSError,ValueError):pass
            time.sleep(.25)
        else:raise RuntimeError('网页服务未就绪，请看logs/web_stderr.log')
    url=f'http://127.0.0.1:{d["http_port"]}/#causal'
    print('已启动：'+url+'；先在网页选择串口，重新上电后点“上电后加载固件”。')
    if not no_browser:webbrowser.open(url)
def stop():
    d=config()
    try:
        info=request(d['http_port']);s=request(d['http_port'],'/api/state')
        if Path(info.get('root','')).resolve()==APP.resolve() and s.get('busy'):
            if s.get('task') not in ('network','capacity'):raise RuntimeError('正在加载/自检，等待完成后再关闭')
            request(d['http_port'],'/api/stop',{})
            deadline=time.monotonic()+70
            while time.monotonic()<deadline:
                if not request(d['http_port'],'/api/state').get('busy'):break
                time.sleep(.3)
            else:raise RuntimeError('实验尚未停止，不强制结束服务')
    except (OSError,ValueError):pass
    current=services()
    for name,row in list(current.items()):
        actual=proc_path(row['pid']);expected=Path(row['exe']).resolve()
        if actual==expected and expected.is_relative_to(ROOT):
            k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p;k.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint];k.CloseHandle.argtypes=[ctypes.c_void_p]
            h=k.OpenProcess(1,False,row['pid'])
            if h:
                try:k.TerminateProcess(h,0)
                finally:k.CloseHandle(h)
        current.pop(name)
    write(ROOT/'services.json',current);print('本包后台服务已停止。')
def menu():
    while True:
        print('\n蜂群通信实验室 · 便携演示版\n1 检查文件与运行环境\n2 设置串口、加载工具和板卡\n3 启动完整系统（含本地AI）\n4 停止本包服务\n5 打开运行说明\n6 打开本机结果文件夹\n0 退出菜单（服务继续运行）')
        try:
            a=input('输入编号：').strip()
            if a=='0':return
            if a=='1':check()
            elif a=='2':setup()
            elif a=='3':start()
            elif a=='4':stop()
            elif a=='5':os.startfile(ROOT/'当前运行与验收说明.txt')
            elif a=='6':os.startfile(APP/'results')
        except Exception as e:print('未完成：'+str(e))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--action',choices=['check','setup','start','stop','ai']);p.add_argument('--no-browser',action='store_true');a=p.parse_args()
    try:
        if not a.action:menu()
        elif a.action=='check':check()
        elif a.action=='setup':setup()
        elif a.action=='start':start(a.no_browser)
        elif a.action=='stop':stop()
        elif a.action=='ai':ai(config())
    except Exception as e:print('未完成：'+str(e));sys.exit(1)
