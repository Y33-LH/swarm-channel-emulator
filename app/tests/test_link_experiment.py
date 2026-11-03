"""Contract negatives and deterministic stimulus; hardware is verified separately."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import link_experiment as le


class ContractTest(unittest.TestCase):
    def test_all_directed_edges_and_real_frame_address(self):
        seen=set()
        for link in range(32):
            p=le.plan(dict(link_id=link))
            e=p["link"];b=bytes.fromhex(p["trials"][0]["tx_hex"])
            self.assertEqual(b[4:8],bytes([e["tx"],e["rx"],e["tx"],e["rx"]]))
            self.assertEqual(len(b),96)
            seen.add((e["tx"],e["rx"]))
        self.assertEqual(len(seen),32)
        self.assertEqual(le.edge(3)["rx"],0)
        self.assertEqual(le.edge(19)["tx"],0)

    def test_immutable_reproduction_and_paired_noise(self):
        a=le.plan(dict(config={"sigma":0},seed=4294967295,frames=10))
        b=le.plan(dict(config={"sigma":2800},seed=4294967295,frames=10))
        self.assertEqual(a,le.validate_saved_plan(copy.deepcopy(a)))
        for x,y in zip(a["trials"],b["trials"]):
            self.assertEqual(x["tx_hex"],y["tx_hex"])
            self.assertEqual(x["noise_seed"],y["noise_seed"])
        self.assertEqual(len({x["noise_seed"] for x in a["trials"]}),10)
        a["trials"][0]["registers"]["68"]=1
        with self.assertRaises(ValueError):le.validate_saved_plan(a)

    def test_reject_invalid_input_before_hardware(self):
        for req in ({"link_id":32},{"link_id":True},{"frames":1.5},{"frames":0},
                    {"seed":0},{"text":"中"*22},{"config":{"gain":float("nan")}},
                    {"config":{"sigma":1.2}},{"config":{"fec":.5}},
                    {"config":{"invented":1}},{"pretend_applied":True}):
            with self.subTest(req=req),self.assertRaises(ValueError):le.plan(req)

    def test_no_start_on_failed_readback(self):
        writes=[]
        def cmd(t):
            writes.append(t)
            if t=="STATUS":return dict(ok=1,status=0,generation=8)
            if t.startswith("READ "):return dict(ok=1,offset=int(t.split()[1]),value=999)
            return dict(ok=1)
        p=le.plan({})
        with self.assertRaisesRegex(RuntimeError,"读回"):
            le.acquire(cmd,p,p["trials"][0],"link_test")
        self.assertNotIn("START",writes)

    def test_reject_wrong_result_generation(self):
        p=le.plan({});regs=p["trials"][0]["registers"];started=False
        def cmd(t):
            nonlocal started
            if t=="START":started=True
            if t=="STATUS":return dict(ok=1,status=2 if started else 0,generation=9 if started else 8)
            if t.startswith("READ "):
                k=t.split()[1];return dict(ok=1,offset=int(k),value=regs[k])
            if t=="RESULT":return dict(type="RESULT",version=le.VERSION,generation=8,tag=1001)
            return dict(ok=1)
        with self.assertRaisesRegex(RuntimeError,"帧代号"):
            le.acquire(cmd,p,p["trials"][0],"link_test")

    def test_reject_mixed_iq_banks(self):
        p=le.plan({});regs=p["trials"][0]["registers"];started=False
        def cmd(t):
            nonlocal started
            if t=="START":started=True
            if t=="STATUS":return dict(ok=1,status=2 if started else 0,generation=9 if started else 8)
            if t.startswith("READ "):
                k=t.split()[1];return dict(ok=1,offset=int(k),value=1 if k=="100" else regs[k])
            if t=="RESULT":return dict(type="RESULT",version=le.VERSION,generation=9,tag=1001)
            if t=="PHYSTATS":return dict(ok=1,version=le.VERSION,fec_mode=1,iq_count=2)
            if t.startswith("IQ "):return dict(ok=1,source="FPGA_SAMPLE_RAM",generation=10,offset=0,equalized=0,iq=[[1,2],[3,4]])
            return dict(ok=1)
        with self.assertRaisesRegex(RuntimeError,"采样帧"):
            le.acquire(cmd,p,p["trials"][0],"link_test")

    def test_capture_failure_counted_not_zero_ber(self):
        obs=[dict(delivered=False,captured=False,payload_bytes=5,
                  phy=dict(pre_bits=0,pre_errors=0,post_bits=0,post_errors=0))]
        s=le.summary(obs)
        self.assertEqual(s["failed"],1);self.assertEqual(s["delivery_rate"],0)
        self.assertIsNone(s["pre_ber"]);self.assertIsNone(s["post_ber"])

    def test_comparison_requires_matching_firmware(self):
        p=le.plan(dict(frames=1))
        o=dict(delivered=False,captured=False,payload_bytes=5,measurement_sha256="same",
               phy=dict(pre_bits=0,pre_errors=0,post_bits=0,post_errors=0))
        a=dict(id="a",plan=p,observations=[o],report={"images":{"bit":"one"}})
        b=dict(id="b",plan=p,observations=[o],report={"images":{"bit":"two"}})
        self.assertFalse(le.compare(a,b)["exact_measurement_reproduced"])
        b["report"]=copy.deepcopy(a["report"])
        self.assertTrue(le.compare(a,b)["exact_measurement_reproduced"])

if __name__=="__main__":unittest.main()
