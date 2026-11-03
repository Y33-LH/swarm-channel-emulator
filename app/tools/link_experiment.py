"""Versioned, frame-coherent single-hop experiments using the current PL/ARM.

The link is an addressed logical edge carried in the actual transmitted bytes.
This isolated fixture does not advance NET, execute a UAV command, or claim a
network ACK. All FPGA transactions use the server's exclusive board owner.
"""
import binascii
import hashlib
import json
import math
import struct
import time

SCHEMA = "swarm.link-experiment.v2"
OBS_SCHEMA = "swarm.frame-observation.v1"
from firmware_contract import VERSION
FS = 8000000
DEFAULT = dict(gain=0.6, sigma=0, delay=24, phase=25, cfo=400,
               echo_gain=0.0, echo_delay=4, echo_phase=90, fec=1, modem_profile=0)
SPEC = dict(gain=(0, 1), sigma=(0, 8192), delay=(0, 512), phase=(-180, 180),
            cfo=(-6000, 6000), echo_gain=(0, 1), echo_delay=(0, 32),
            echo_phase=(-180, 180), fec=(0, 1), modem_profile=(0, 1))
INTEGER = {"sigma", "delay", "echo_delay", "fec", "modem_profile"}
SCOPE = ("独立单跳实板实验：PC 提供测试正文，ARM 写入共享 FPGA 收发核；"
         "链路编号写入实际帧头。没有推进16节点网络，无ACK或端到端送达结论。")


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def edge(link_id):
    if type(link_id) is not int or not 0 <= link_id < 32:
        raise ValueError("请选择 0—31 的有向链路")
    tx = link_id % 16 + 1
    rx = tx + 1 if tx % 4 else 0
    if link_id >= 16:
        tx, rx = rx, tx
    return dict(link_id=link_id, tx=tx, rx=rx,
                channel_class="air_ground" if link_id % 4 == 3 else "air_air")


def channel_config(data):
    if not isinstance(data, dict) or set(data) - set(SPEC):
        raise ValueError("信道配置包含未知字段")
    out = {}
    for k, (lo, hi) in SPEC.items():
        v = data.get(k, DEFAULT[k])
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"{k} 必须在 {lo}—{hi} 之间")
        if k in INTEGER:
            if int(v) != v:
                raise ValueError(f"{k} 必须为整数")
            v = int(v)
        out[k] = v
    return out


def registers(c, seed):
    raw = {12: 0, 48: 5000000, 64: round(c["gain"] * 32768), 68: c["sigma"], 72: 0,
           80: 0, 84: round(c["phase"] / 360 * 2**32), 88: seed,
           92: round(c["cfo"] / FS * 2**32), 96: 0, 112: c["delay"], 116: 0,
           120: round(c["echo_gain"] * 32768), 124: c["echo_delay"],
           128: round(c["echo_phase"] / 360 * 2**32),
           132: round(c["cfo"] / FS * 2**32), 136: 0, 140: 0,
           192: c["fec"], 772: 0, 776: c["modem_profile"], 796: 0}
    return {str(k): int(v) & 0xFFFFFFFF for k, v in raw.items()}


def plan(request):
    if not isinstance(request, dict) or set(request) - {"link_id", "text", "seed", "frames", "config"}:
        raise ValueError("实验请求包含未知字段")
    link = edge(request.get("link_id", 0))
    text = request.get("text", "位置正常，保持通信")
    if not isinstance(text, str) or not 1 <= len(text.encode("utf-8")) <= 64:
        raise ValueError("正文须为 1—64 个 UTF-8 字节；中文约 21 字")
    seed, count = request.get("seed", 20261020), request.get("frames", 3)
    if type(seed) is not int or not 1 <= seed <= 0xFFFFFFFF:
        raise ValueError("种子须为 1—4294967295 的整数")
    if type(count) is not int or not 1 <= count <= 10:
        raise ValueError("每次实验采集 1—10 帧，不自动重传")
    cfg = channel_config(request.get("config", {}))
    payload = text.encode()
    # Stable wire run/sequence/time fields: rerun uses identical bytes, never wall time.
    wire_run = int(digest(dict(link=link, text=text, seed=seed))[:8], 16)
    trials = []
    for i in range(count):
        tag, noise_seed = 1001 + i, ((seed - 1 + i * 773) % 0xFFFFFFFF) + 1
        header = struct.pack("<BBBBBBBBIIHHQHBB", 1, 5, 0, 1,
                             link["tx"], link["rx"], link["tx"], link["rx"],
                             wire_run, tag, 0, 1, 0, len(payload), 0, 0)
        tx = header + payload + bytes(64-len(payload))
        trials.append(dict(index=i, tag=tag, noise_seed=noise_seed, tx_hex=tx.hex(),
                           registers=registers(cfg, noise_seed)))
    body = dict(schema=SCHEMA, link=link, text=text, seed=seed, frames=count, config=cfg,
                trials=trials, timebase="frame_index; no network model time is advanced",
                scope=SCOPE)
    body["plan_sha256"] = digest(body)
    return body


def validate_saved_plan(p):
    rebuilt = plan(dict(link_id=p["link"]["link_id"], text=p["text"], seed=p["seed"],
                        frames=p["frames"], config=p["config"]))
    if rebuilt != p:
        raise ValueError("保存的实验计划不完整、被修改或与当前接口版本不兼容")
    return rebuilt


def applied_channel(reg):
    signed = lambda v: v - 2**32 if v >= 2**31 else v
    return dict(gain0=reg["64"]/32768, gain1=reg["120"]/32768, sigma=reg["68"],
                delay_samples=reg["112"], echo_delay_samples=reg["124"],
                phase_radians=reg["84"]*math.tau/2**32,
                echo_phase_radians=reg["128"]*math.tau/2**32,
                cfo_hz=signed(reg["92"])*FS/2**32, echo_cfo_hz=signed(reg["132"])*FS/2**32,
                fec=reg["192"], modem_profile=reg["776"],
                source="FPGA_REGISTER_READBACK", applied=True)


def acquire(cmd, p, trial, experiment_id, cancel=lambda: False, progress=lambda x: None):
    """No writes/start between the readback, RESULT, PHYSTATS and both IQ banks."""
    def good(command):
        r = cmd(command)
        if r.get("ok") != 1:
            raise RuntimeError(f"{command}: {r}")
        return r

    def read(offset):
        r = good(f"READ {offset}")
        if r.get("offset") != offset:
            raise RuntimeError("寄存器回复地址与请求不一致")
        return r["value"]

    if cancel():
        raise InterruptedError("用户中止实验")
    good("RELEASE")
    before = good("STATUS")
    if before["status"] & 1:
        raise RuntimeError("FPGA 尚忙，不能改变参数")
    for k, v in trial["registers"].items():
        good(f"WRITE {k} {v}")
    actual = {k: read(int(k)) for k in trial["registers"]}
    if actual != trial["registers"]:
        raise RuntimeError("参数写入与FPGA读回不一致，未启动发送")
    applied_at = time.time()
    progress(dict(phase="applied", frame_index=trial["index"], applied_registers=actual))
    good(f'LOAD {trial["tag"]} {trial["tx_hex"]}')
    if cancel():
        raise InterruptedError("用户中止实验；本帧尚未发送")
    started = time.monotonic()
    good("START")
    deadline = started + 8
    while True:
        status = good("STATUS")
        if status["status"] & 2:
            break
        if cancel():
            good("ABORT")
            raise InterruptedError("用户中止实验")
        if time.monotonic() > deadline:
            good("ABORT")
            raise TimeoutError("FPGA 接收完成超时")
    result = cmd("RESULT")  # A channel failure is a valid observation, not an API error.
    expected_generation = (before["generation"] + 1) & 0xFFFFFFFF
    generation = result.get("generation")
    if (result.get("type") != "RESULT" or result.get("version") != VERSION
            or generation != expected_generation or status["generation"] != generation
            or result.get("tag") != trial["tag"]):
        raise RuntimeError("接收结果的帧代号／标签／固件不匹配，拒绝发布")
    phy = good("PHYSTATS")
    if phy["version"] != VERSION or phy["fec_mode"] != actual["192"]:
        raise RuntimeError("接收统计的固件／纠错配置不匹配")
    captures = read(100)
    count = phy["iq_count"]
    if type(count) is not int or not 0 <= count <= 512:
        raise RuntimeError("采样长度异常")
    iq = {}
    for bank in (0, 1):
        points = []
        for off in range(0, count, 64):
            n = min(64, count - off)
            chunk = good(f"IQ {off} {n} {bank}")
            if (chunk.get("source") != "FPGA_SAMPLE_RAM" or chunk.get("generation") != generation
                    or chunk.get("offset") != off or chunk.get("equalized") != bank
                    or len(chunk.get("iq", [])) != n):
                raise RuntimeError("采样帧、样本偏移、库或长度不匹配")
            if any(not isinstance(v, list) or len(v) != 2 or
                   any(type(x) is not int or not -32768 <= x <= 32767 for x in v) for v in chunk["iq"]):
                raise RuntimeError("I/Q 样本格式异常")
            points.extend(chunk["iq"])
        iq["received" if bank == 0 else "equalized"] = points
    after = good("STATUS")
    final_actual = {k: read(int(k)) for k in actual}
    if after["generation"] != generation or not after["status"] & 2 or final_actual != actual:
        raise RuntimeError("采集期间帧或参数发生变化，拒绝拼接观测")
    tx = bytes.fromhex(trial["tx_hex"])
    rx = bytes.fromhex(result.get("rx_hex", ""))
    crc = binascii.crc_hqx(tx, 0xFFFF)
    match = bool(result.get("ok"))
    if match and not (rx == tx and result.get("crc_calc") == result.get("crc_recv") == crc
                      and result.get("rx_len") == len(p["text"].encode())
                      and result.get("rx_frame_bytes") == 96 and result["result_code"] == 0):
        raise RuntimeError("固件声明有效，但独立字节／长度／CRC核验失败")
    if not match and rx:
        raise RuntimeError("失败帧仍交付了正文")
    failure = None if match else ("frame_capture" if not captures else "decode_or_crc")
    observed = dict(schema=OBS_SCHEMA, experiment_id=experiment_id,
                    observation_id=f"{experiment_id}:frame:{trial['index']}",
                    plan_sha256=p["plan_sha256"], link=p["link"], frame_index=trial["index"],
                    tag=trial["tag"], generation=generation, source="physical_board_UART",
                    model_time_ms=None, applied_at_unix=applied_at, captured_at_unix=time.time(),
                    acquisition_wall_s=time.monotonic()-started, config_verified=True,
                    applied_registers=actual, channel=applied_channel(actual),
                    same_frame_verified=True, sample_count=count, phy=phy, iq=iq,
                    captured=bool(captures), result=result, tx_hex=tx.hex(),
                    expected_crc16=crc, delivered=match, failure_stage=failure,
                    payload_bytes=len(p["text"].encode()), received_text=p["text"] if match else None)
    # Fingerprint includes raw received data, estimates, all samples and counters;
    # only absolute hardware generation and wall clock are intentionally excluded.
    observed["measurement_sha256"] = digest(measurement(observed))
    return observed


def measurement(o):
    result = {k: v for k, v in o["result"].items() if k != "generation"}
    return {k: o[k] for k in ("link", "frame_index", "tag", "applied_registers",
                              "phy", "iq", "captured", "delivered", "tx_hex", "failure_stage")} | {"result": result}


def summary(observations):
    n = len(observations)
    good = sum(x["delivered"] for x in observations)
    pre_bits = sum(x["phy"]["pre_bits"] for x in observations if x["captured"])
    pre_err = sum(x["phy"]["pre_errors"] for x in observations if x["captured"])
    post_bits = sum(x["phy"]["post_bits"] for x in observations if x["captured"])
    post_err = sum(x["phy"]["post_errors"] for x in observations if x["captured"])
    evm_symbols = sum(x["phy"].get("evm_symbols", 0) for x in observations if x["captured"])
    evm_sum = sum(x["phy"].get("evm_error_sum", 0) for x in observations if x["captured"])
    return dict(attempts=n, captured=sum(x["captured"] for x in observations), delivered=good,
                delivery_rate=good/n if n else None, failed=n-good,
                delivered_payload_bytes=sum(x["payload_bytes"] for x in observations if x["delivered"]),
                pre_ber=pre_err/pre_bits if pre_bits else None,
                post_ber=post_err/post_bits if post_bits else None,
                payload_evm_percent=100*math.sqrt(evm_sum/(evm_symbols*8192**2)) if evm_symbols else None,
                ber_scope="captured frames only; failed captures are counted separately",
                retries=0, scope="single_hop_payload; not network ACK / end-to-end delivery")


def compare(left, right):
    a, b = left["plan"], right["plan"]
    changes = {k: dict(before=a["config"][k], after=b["config"][k])
               for k in SPEC if a["config"][k] != b["config"][k]}
    same_stimulus = (a["link"] == b["link"] and a["frames"] == b["frames"]
                     and all(x["tx_hex"] == y["tx_hex"] and x["noise_seed"] == y["noise_seed"]
                             for x, y in zip(a["trials"], b["trials"])))
    rows_a, rows_b = left["observations"], right["observations"]
    complete = len(rows_a) == a["frames"] and len(rows_b) == b["frames"]
    images_a = (left.get("report") or {}).get("images")
    images_b = (right.get("report") or {}).get("images")
    same_images = bool(images_a and images_a == images_b)
    equal = same_images and same_stimulus and not changes and complete and all(
        x["measurement_sha256"] == y["measurement_sha256"] for x, y in zip(rows_a, rows_b))
    return dict(left_id=left["id"], right_id=right["id"], changed_config=changes,
                same_stimulus=same_stimulus, same_firmware=same_images, complete=complete,
                single_setting_comparison=bool(complete and same_images and same_stimulus and len(changes) == 1),
                exact_measurement_reproduced=bool(equal),
                left=summary(rows_a), right=summary(rows_b),
                caveat="小样本对照，不作为统计可靠率或等能量纠错增益证明")
