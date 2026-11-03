"""重新生成链路传输验证样本（2026-10-25）：内容与业务直接相关。

- source_audio.wav：SAPI 合成中文语音「链路验证通过」（8 kHz 单声道，≤8192 字节，
  满足固件 AUDIO_MAX 与验收的 8000 Hz 检查）；SAPI 不可用时降级为提示音。
- source_video.webm：cv2 生成 20 帧动画——一个报文沿节点 1→2→3→4→地面逐跳前进，
  带帧号与跳数标注（验收要求恰好 20 帧且 cv2 可解码）。

样本用途不变：证明分片 / 多跳转发 / 地面重组；尺寸上限由固件决定，与业务回放互补。
"""
import json, subprocess, sys, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / 'media'
SR = 8000

def synth_speech(text, tmp):
    ps = ("[Console]::InputEncoding=[Text.Encoding]::UTF8;"
          "Add-Type -AssemblyName System.Speech;"
          "$v=New-Object System.Speech.Synthesis.SpeechSynthesizer;$v.Rate=3;"
          "$v.SetOutputToWaveFile('%s');$v.Speak([Console]::In.ReadToEnd());$v.Dispose()"
          % str(tmp).replace('\\', '\\\\'))
    subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                   input=text.encode('utf-8'), timeout=30, check=True, capture_output=True)

def make_audio():
    import numpy as np, wave
    speech = False
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tf:
            tmp = tf.name
        synth_speech('链路验证通过', tmp)
        with wave.open(tmp) as w:
            fr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        os.unlink(tmp)
        a = np.frombuffer(raw, dtype=np.int16 if sw == 2 else np.uint8).astype(np.float64)
        if sw == 1:
            a = (a - 128) * 256
        if ch > 1:
            a = a.reshape(-1, ch).mean(1)
        xi = np.arange(max(1, int(len(a) * SR / fr))) / SR
        a = np.interp(xi, np.arange(len(a)) / fr, a) / 32768
        speech = True
    except Exception as e:
        print('  SAPI 不可用，降级为提示音：', e)
        t = np.arange(int(0.9 * SR)) / SR
        a = 0.6 * np.sin(2 * np.pi * 660 * t) * np.minimum(1, t * 40) * np.exp(-t * 2)
    maxn = 7990  # 8192 上限 − WAV 头
    a = a[:maxn]
    peak = float(np.abs(a).max()) or 1.0
    pcm = (a / peak * 0.9 * 127 + 128).astype(np.uint8)
    out = MEDIA / 'source_audio.wav'
    with wave.open(str(out), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print('  audio:', out.stat().st_size, 'bytes, speech =', speech)

def make_video():
    import cv2
    import numpy as np
    out = MEDIA / 'source_video.webm'
    W, H, N = 320, 240, 20
    vw = None
    for fourcc_name in ('VP80', 'VP90', 'mp4v'):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_name)
        vw = cv2.VideoWriter(str(out), fourcc, 10, (W, H))
        if vw.isOpened():
            print('  codec:', fourcc_name)
            break
        vw.release(); vw = None
    if vw is None:
        raise RuntimeError('无可用视频编码器')
    # 五站：节点1 → 2 → 3 → 4 → 地面
    stations = [(30, 60), (100, 60), (170, 60), (240, 60), (290, 180)]
    names = ['01', '02', '03', '04', 'GND']
    for f in range(N):
        img = np.full((H, W, 3), (25, 15, 4), np.uint8)  # BGR 深色底
        for i, (x, y) in enumerate(stations):
            cv2.circle(img, (x, y), 12, (160, 120, 60), 2)
            cv2.putText(img, names[i], (x - 10, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 220, 230), 1)
            if i:
                cv2.line(img, stations[i - 1], stations[i], (60, 80, 100), 1)
        hop = min(4, f // 4)  # 每 4 帧前进一跳
        frac = (f % 4) / 3.0
        x0, y0 = stations[hop - 1] if hop else stations[0]
        x1, y1 = stations[hop]
        px, py = int(x0 + (x1 - x0) * frac), int(y0 + (y1 - y0) * frac)
        cv2.rectangle(img, (px - 5, py - 5), (px + 5, py + 5), (80, 245, 210), -1)  # BGR 青绿色报文块
        cv2.putText(img, 'frame %02d/20  hop %d->%d' % (f + 1, hop, hop + 1), (8, H - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 170, 190), 1)
        cv2.putText(img, 'swarm link sample', (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (140, 170, 190), 1)
        vw.write(img)
    vw.release()
    cap = cv2.VideoCapture(str(out))
    frames = 0
    while cap.read()[0]:
        frames += 1
    cap.release()
    assert frames == N, f'解码帧数 {frames} != {N}'
    print('  video:', out.stat().st_size, 'bytes,', frames, 'frames decoded ok')

def main():
    make_audio()
    make_video()
    import hashlib
    manifest = {
        'audio': {'file': 'source_audio.wav',
                  'bytes': (MEDIA / 'source_audio.wav').stat().st_size,
                  'sha256': hashlib.sha256((MEDIA / 'source_audio.wav').read_bytes()).hexdigest(),
                  'source': 'SAPI-synthesized Chinese speech "链路验证通过" (tone fallback)'},
        'video': {'file': 'source_video.webm',
                  'bytes': (MEDIA / 'source_video.webm').stat().st_size,
                  'sha256': hashlib.sha256((MEDIA / 'source_video.webm').read_bytes()).hexdigest(),
                  'frames': 20,
                  'source': 'generated 4-hop packet animation matching the node 1 chain, not camera footage'},
    }
    (MEDIA / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print('manifest updated')

if __name__ == '__main__':
    main()
