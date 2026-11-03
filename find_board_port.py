"""扫描本机所有串口，自动定位蜂群实验板的 ARM 调试串口。

用途：换 USB 口 / 换电脑后 COM 号会变，不再需要手工猜端口号。
用法：
    runtime/python/python.exe find_board_port.py            # 报告模式
    runtime/python/python.exe find_board_port.py --quiet    # 只打印端口号，便于脚本取用
    runtime/python/python.exe find_board_port.py --all      # 连没响应 PING 的口也一并列出
不修改工程内任何现有文件，仅向 logs/last_port.txt 写入探测结果。
"""
import sys, os, time, glob

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(BASE, 'app/tools/python_deps')]

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print('IMPORT_FAILED', e)
    sys.exit(2)

BAUD = 230400
# 板卡 PING 响应里必然出现的特征串（见 app/sw/main.c 的 PING 分支）
MARKERS = (b'protocol', b'pl_hz', b'arm_build', b'swarm')


def candidate_ports():
    """Windows 用 \\\\.\\COMxx 前缀保证 COM10 以上也能打开；同时给出枚举到的型号说明。"""
    info = {}
    for p in list_ports.comports():
        info[p.device] = (p.description or '') + ' ' + (p.manufacturer or '') + ' ' + (p.hwid or '')
    ports = sorted(info, key=lambda s: int(''.join(ch for ch in s if ch.isdigit()) or 0))
    # 补充：部分驱动不出现在枚举里，直接扫 COM1..COM32
    for i in range(1, 33):
        c = 'COM%d' % i
        if c not in ports:
            ports.append(c)
    return ports, info


def probe(device):
    """向某端口发 PING，返回 (状态, 响应文本)。"""
    try:
        s = serial.Serial(device, BAUD, timeout=0.6, write_timeout=0.6)
    except Exception as e:
        return 'unopenable', str(e)
    try:
        try:
            s.reset_input_buffer()
        except Exception:
            pass
        s.write(b'PING\n')
        s.flush()
        t0 = time.monotonic()
        data = b''
        while time.monotonic() - t0 < 2.5:
            b = s.read(1)
            if not b:
                continue
            data += b
            if data.endswith(b'\n'):
                break
        if not data:
            return 'silent', ''
        if any(m in data for m in MARKERS):
            return 'board', data.decode('utf-8', 'replace').strip()
        return 'other', data.decode('utf-8', 'replace').strip()[:120]
    except Exception as e:
        return 'error', type(e).__name__ + ': ' + str(e)
    finally:
        try:
            s.close()
        except Exception:
            pass


def main():
    quiet = '--quiet' in sys.argv
    show_all = '--all' in sys.argv
    ports, info = candidate_ports()
    found = []
    others = []

    for dev in ports:
        st, txt = probe(dev)
        if st == 'board':
            found.append((dev, txt, info.get(dev, '')))
        elif st == 'silent':
            others.append((dev, '(无响应)', info.get(dev, '')))
        elif show_all:
            others.append((dev, st + ' ' + txt, info.get(dev, '')))

    if quiet:
        if found:
            print(found[0][0])
        sys.exit(0 if found else 1)

    print('=== 蜂群实验板串口探测（%d 波特 / 8N1）===' % BAUD)
    if found:
        print('\n[命中] 以下端口响应了板卡 PING：')
        for dev, txt, desc in found:
            print('  %s' % dev)
            print('    响应：%s' % txt)
            if desc.strip():
                print('    设备：%s' % desc.strip())
        if len(found) > 1:
            print('\n  注意：检测到多个，请取插在板载 UART 上的那个（CH340 通常为板载调试串口）。')
    else:
        print('\n[未命中] 没有找到响应 PING 的端口。请检查：')
        print('  1. 板子已上电，USB 线接的是板载 UART 口（不是 JTAG 口）；')
        print('  2. 驱动已装（设备管理器里能看到 USB-SERIAL CH340）；')
        print('  3. 没有其他程序（串口助手、旧的服务进程）占用该串口；')
        print('  4. 板内固件已加载（未加载时不会响应 PING）。')

    if show_all or (not found and others):
        print('\n[其他] 已扫描但非本板串口：')
        for dev, txt, desc in others[:12]:
            line = '  %-8s %s' % (dev, txt)
            if desc.strip():
                line += '  | ' + desc.strip()[:60]
            print(line)

    # 记录结果，供后续脚本取用
    try:
        os.makedirs(os.path.join(BASE, 'logs'), exist_ok=True)
        with open(os.path.join(BASE, 'logs/last_port.txt'), 'w', encoding='utf-8') as f:
            f.write((found[0][0] if found else '') + '\n')
    except Exception:
        pass

    if found:
        dev = found[0][0]
        print('\n=== 下一步 ===')
        print('  实板连接：浏览器打开后，在页面里填串口 %s，或用命令行：' % dev)
        print('    runtime/python/python.exe -X utf8 -B portable_server.py --http 18878 --port %s' % dev)
        print('  （野火 7020 板卡需先设置环境变量 SWARM_BOARD_PROFILE=wildfire7020）')
    sys.exit(0 if found else 1)


if __name__ == '__main__':
    main()
