"""把固件返回的裸错误翻译成用户看得懂的中文。

板上固件在出错时只会回一串这样的东西：

    ('SCENECFG 010000000100...', {'ok': 0, 'type': 'SCENECFG', 'error_code': 2, 'config_id': 2429128425})

一行 128 位十六进制加一个没有解释的错误码，直接甩给用户。这个模块负责把它
翻译成「哪一项、什么值、允许范围是多少」。

错误码含义与 sw/scene_product.c 的 scene_configure() 保持一致：
    1  场景配置字符串长度或格式不对
    2  某一项超出板卡允许范围
    3  编队/运动余量超出 10 km x 10 km 边界
    4  实验正在运行，不允许改场景
    5  外部注入节点不能是 9 或 13（这两个是 FPGA 硬件端点）
"""
import ast

# 与 sw/scene_product.c 的 low[]/high[] 以及 tools/product_config.py 的 limits 一致
SCENE_LIMITS = [
    ('schema', '协议版本', 1, 1),
    ('environment', '信道环境', 0, 7),
    ('weather', '天气', 0, 7),
    ('formation', '编队', 0, 8),
    ('spacing_m', '节点间距(米)', 150, 1100),
    ('altitude_m', '飞行高度(米)', 100, 800),
    ('center_x_m', '区域中心X(米)', 500, 9500),
    ('center_y_m', '区域中心Y(米)', 500, 9500),
    ('speed_mmps', '飞行速度(毫米/秒)', 0, 20000),
    ('heading_deg', '航向(度)', 0, 359),
    ('reference_snr_cdb', '参考信噪比(0.01dB)', 1800, 4500),
    ('faults', '故障注入', 0, 1),
    ('jitter_percent', '位置抖动(%)', 0, 200),
    ('carrier_mhz', '载波频率(MHz)', 200, 6000),
    ('external_node', '外部注入节点', 0, 16),
    ('reserved', '场景快进倍率（0表示1倍）', 0, 64),
]

SCENE_ERROR_TEXT = {
    1: '场景配置字符串长度或格式不正确',
    2: '有参数超出板卡允许范围',
    3: '编队或运动余量超出 10 km x 10 km 边界',
    4: '实验正在运行，不允许修改场景',
    5: '外部注入节点不能是 9 或 13（这两个是 FPGA 硬件端点）',
}

# 常见的固件命令错误 -> 中文
COMMAND_ERRORS = {
    'NETWORK_COMMAND_OR_STATE': '当前状态不接受这条指令',
    'AUDIO_INCOMPLETE': '音频数据没有完整载入，请重新加载媒体素材',
    'VIDEO_INCOMPLETE': '视频数据没有完整载入，请重新加载媒体素材',
    'RANGE': '参数超出允许范围',
    'LINK': '链路编号超出范围',
    'LINK_RANGE': '链路编号必须是 0–31',
    'BATCH': '遥测批次超出范围',
    'FEC_RANGE': '纠错开关只能是 0 或 1',
    'LOAD_RANGE': '负载速率超出范围',
    'NUMBER': '命令行里有非法数字',
    'HEX': '十六进制数据格式错误',
    'MEDIA_SIZE': '媒体数据过长',
    'MEDIA_RANGE': '媒体写入位置或长度超出范围',
    'MISSING_RECEIVED_FRAGMENT': '这一段接收数据还没收到',
    'QUEUE_FULL': '发送队列已满',
    'EXTERNAL_POSITION': '外部节点坐标超出范围',
    'NETWORK_COMMAND_OR_STATE_OR_STATE': '当前状态不接受这条指令',
    'HARDWARE_NODE_INIT': '硬件节点初始化失败',
    'HARDWARE_NODE_RANGE': '硬件节点编号超出范围',
    'SNAPSHOT_OVERFLOW': '遥测报文过长',
}


def _decode_scene(hex_str):
    """把 128 位十六进制解成 [(中文名, 值, 下限, 上限), ...]。"""
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError:
        return None
    if len(raw) != 64:
        return None
    out = []
    for i, (key, name, low, high) in enumerate(SCENE_LIMITS):
        value = int.from_bytes(raw[i * 4:(i + 1) * 4], 'little', signed=True)
        out.append((name, value, low, high, key))
    return out


def _describe_scene(hex_str, code, protocol=17):
    decoded = _decode_scene(hex_str)
    base = SCENE_ERROR_TEXT.get(code, '未知错误码 %s' % code)
    # 4/5 与逐项范围无关，直接给结论，不要再用一大段参数表淹没用户
    if code in (4, 5):
        return '板卡拒绝场景配置：%s。' % base
    if not decoded:
        return '板卡拒绝场景配置：%s' % base
    offenders = [(name, value, low, high) for name, value, low, high, _ in decoded
                 if not low <= value <= high]
    if offenders:
        detail = '；'.join('%s=%s（允许 %s–%s）' % (n, v, lo, hi) for n, v, lo, hi in offenders)
        return '板卡拒绝场景配置：%s —— %s' % (base, detail)
    carrier = next((v for _, v, _, _, k in decoded if k == 'carrier_mhz'), 2400)
    if code == 2 and carrier != 2400 and protocol < 18:
        return ('板卡拒绝场景配置：载波频率 %s MHz 超出板载固件的实际支持范围。'
                '当前固件（协议 %s）的载波寄存器只实现了 2400 MHz 一档，'
                '请把载波改回 2400 MHz 再试。') % (carrier, protocol)
    # 范围检查没抓到时，列出全部值方便定位（固件实际限制可能与文档不一致）
    summary = '，'.join('%s=%s' % (n, v) for n, v, _, _, _ in decoded)
    return ('板卡拒绝场景配置：%s。逐项检查未发现越界，说明板载固件的限制比上位机更严格，'
            '请把下面这行发给技术支持定位：%s') % (base, summary)


def explain(text):
    """把任意可能来自固件的错误串翻译为中文；翻不动就原样返回。"""
    if not isinstance(text, str):
        text = str(text)
    stripped = text.strip()
    # 形如 ('SCENECFG xxx', {...}) 的 Python 元组/字典字面量
    if stripped.startswith('(') and '{' in stripped:
        try:
            parsed = ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            return stripped
        if isinstance(parsed, (tuple, list)) and len(parsed) >= 2 and isinstance(parsed[-1], dict):
            info = parsed[-1]
            head = parsed[0] if isinstance(parsed[0], str) else ''
            code = info.get('error_code')
            kind = info.get('type')
            if kind == 'SCENECFG' or (isinstance(head, str) and head.startswith('SCENECFG')):
                hex_str = head.split(None, 1)[1].strip() if len(head.split(None, 1)) > 1 else ''
                return _describe_scene(hex_str, code if isinstance(code, int) else -1)
            if isinstance(info.get('error'), str):
                key = info['error']
                return '板卡返回 %s：%s' % (key, COMMAND_ERRORS.get(key, key))
            if isinstance(code, int):
                return '板卡返回错误：%s' % SCENE_ERROR_TEXT.get(code, '错误码 %s' % code)
    # 纯字典形式 {'error': 'XXX'}（不带元组前缀）
    if stripped.startswith('{') and stripped.endswith('}'):
        try:
            info = ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            info = None
        if isinstance(info, dict) and isinstance(info.get('error'), str):
            key = info['error']
            return '板卡返回 %s：%s' % (key, COMMAND_ERRORS.get(key, key))
    key = stripped.strip('"\'')
    if key in COMMAND_ERRORS:
        return '板卡返回：%s' % COMMAND_ERRORS[key]
    if stripped.startswith('SCENECFG'):
        parts = stripped.split(None, 1)
        return _describe_scene(parts[1].strip() if len(parts) > 1 else '',
                               _extract_code(stripped))
    return stripped


def _extract_code(text):
    import re
    m = re.search(r"error_code\D+(\d+)", text)
    return int(m.group(1)) if m else -1


def preflight(config, protocol=17):
    """下发前的本地预检，返回问题清单（空列表表示通过）。

    只放「上位机已知、但板上固件会更早拒绝」的约束，避免让用户拿着
    合法-looking 的配置去撞板子。
    """
    problems = []
    if config.get('reserved',0)>1 and (protocol or 17)<22:problems.append('场景快进需要加载协议22或更新固件')
    carrier = config.get('carrier_mhz')
    # 协议 17 的映像只实现 2400 MHz 一档；协议 18 起才开放其它频点
    if isinstance(carrier, int) and carrier != 2400 and (protocol or 17) < 18:
        problems.append(
            '载波频率 %s MHz：当前 board 固件（协议 %s）只支持 2400 MHz，'
            '其它频点会被板卡拒绝。' % (carrier, protocol))
    return problems
