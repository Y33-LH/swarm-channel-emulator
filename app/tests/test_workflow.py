import unittest,copy,sys,struct
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'reference')]
import workflow_context as wc,experiment_comparison as ec,network_intervention as ni,product_assistant as ai,server
from product_config import DEFAULT,config_hash
from test_assistant_live_context import snapshot

def rec(id='network_1',weather=0):
    cfg={**DEFAULT,'weather':weather};s={**snapshot(),'round':1200,'generated':1920,'delivered':1920,'payload_bytes':10000}
    report=dict(pass_=True,config=cfg,config_sha256=config_hash(cfg),seed=7,duration_s=120,ideal=0,
                version='000d0003',protocol=17,image_hashes={'bit':'a','elf':'b','init':'c'},telemetry_rounds=10,final=s)
    return dict(id=id,complete=True,control_history=[],report=report,snapshots=[s],meta=dict(kind='network',release_sha256='software-a'))

class WorkflowTests(unittest.TestCase):
    def test_network_ground_ack_exposes_measured_effect_without_future_leak(self):
        from test_action_context import snap
        ss=[snap(t,2 if t>=12 else 1) for t in range(1,30)]
        for s in ss:
            s['watch_link']=4;s['repeat_media']=True
            s['business_counts'][1][1]=min(s['round']//10,12)*5+max(0,s['round']//10-12)
        wire=struct.pack('<5I',1,5,4,1,10000).hex()
        control=dict(round=100,command='GCOMMAND '+wire,response={'ok':1})
        r=dict(snapshots=ss,report={'config':DEFAULT},control_history=[control])
        early=wc.select({'context':dict(record_id='network_1',mode='history',model_ms=15000,link=4)}, {}, None,lambda _:r,None)
        late=wc.select({'context':dict(record_id='network_1',mode='history',model_ms=25000,link=4)}, {}, None,lambda _:r,None)
        self.assertIsNone(early['identity']['effects'][0]['after'])
        effect=late['identity']['effects'][0]
        self.assertEqual(effect['verdict'],'measured');self.assertEqual(effect['after']['generated_fragments_per_s'],1)
        self.assertEqual(effect['before']['generated_fragments_per_s'],5)
        self.assertEqual(wc.control_events([{**control,'response':{'ok':0}}]),[])
    def test_preparation_retires_previous_observations_before_worker(self):
        before=copy.deepcopy(server.state)
        try:
            server.state.update(snapshot=snapshot(),network_record_id='causal_old',snapshots=[snapshot()])
            with patch.object(server.threading,'Thread'):
                server.begin('network',lambda:None)
            self.assertIsNone(server.state['snapshot']);self.assertIsNone(server.state['network_record_id'])
            self.assertEqual(server.state['snapshots'],[])
            with self.assertRaises(ValueError):wc.select({'context':{'record_id':'causal_old'}},server.state,None,None,None)
        finally:
            if server.owner.locked():server.owner.release()
            server.state.clear();server.state.update(before)
    def test_history_has_exact_time_and_no_future(self):
        a=snapshot();b={**snapshot(),'round':300,'command_results':[[1,5,4,1,2,29000]]};r=dict(snapshots=[a,b],report={'config':DEFAULT})
        c=wc.select(dict(context=dict(record_id='network_1',mode='history',model_ms=20000,link=0)),{},None,lambda _:r,None)
        self.assertEqual(c['snapshot']['round'],200);self.assertFalse(c['snapshot'].get('command_results'))
        with patch.object(ai,'available',return_value={'available':False}):ans=ai.answer('暂停节点5的视频',c['snapshot'],DEFAULT,context=c['identity'])
        self.assertFalse(any(x.get('action') for x in ans['evidence']));self.assertIn('只读历史',ans['answer'])
    def test_missing_and_wrong_context_rejected(self):
        state=dict(network_record_id='network_2',snapshot=snapshot(),config=DEFAULT)
        with self.assertRaises(ValueError):wc.select({'context':{'record_id':'network_1'}},state,None,None,None)
        with self.assertRaises(ValueError):wc.select({'context':{'model_ms':90000}},state,None,None,None)
    def test_other_link_does_not_reuse_receiver(self):
        state=dict(network_record_id='network_2',snapshot=snapshot(),config=DEFAULT)
        c=wc.select({'context':{'link':7}},state,None,None,None)
        self.assertEqual(c['snapshot']['watch_phy'],[]);self.assertTrue(state['snapshot']['watch_phy'])
    def test_rate_and_height_mode_boundary(self):
        ctx=dict(geometry_locked=True,mode='current')
        with patch.object(ai,'available',return_value={'available':False}):
            a=ai.answer('把节点5媒体生成速率降到1分片/秒',snapshot(),DEFAULT,context=ctx)
            h=ai.answer('让节点9高度设为450米',snapshot(),DEFAULT,context=ctx)
            valid=ai.answer('把节点5媒体速率设为9分片/秒',snapshot(),DEFAULT,context=ctx)
            bad=ai.answer('把节点5媒体速率设为31分片/秒',snapshot(),DEFAULT,context=ctx)
        self.assertEqual(next(x['action'] for x in a['evidence'] if x['id']=='command_proposal')['value'],1)
        self.assertEqual(next(x['action'] for x in valid['evidence'] if x['id']=='command_proposal')['value'],9)
        self.assertFalse(any(x.get('action',{}).get('opcode')==5 for x in h['evidence'] if x.get('action')))
        self.assertIn('整机',h['answer']);self.assertFalse(any(x.get('action') for x in bad['evidence']))
    def test_comparison_distinguishes_repeat_single_and_mixed(self):
        a=rec();b=rec('network_2',4)
        self.assertEqual(ec.compare(a,copy.deepcopy(a))['mode'],'repeat')
        r=ec.compare(a,b);self.assertEqual(r['mode'],'single_setting');self.assertTrue(r['composite_preset'])
        b['report']['seed']=8;self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
        b=rec('network_2',4);b['meta']['release_sha256']='different';self.assertIn('release_sha256',ec.compare(a,b)['changed_conditions'])
    def test_incomplete_tampered_and_commands_are_not_fair(self):
        a=rec();b=rec('network_2',4);b['complete']=False;self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
        b=rec('network_2',4);b['report']['config_sha256']='bad';self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
        b=rec('network_2',4);b['report']['final']['command_results']=[[1,5,4,1,2,29000]];self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
    def test_old_ai_proposal_cannot_cross_run_or_history(self):
        server.assistant_jobs['x']=dict(record_id='network_old',run_id=41,as_of_model_ms=20000,context=dict(mode='history'),provisional=dict(evidence=[]))
        with self.assertRaisesRegex(ValueError,'历史'):server.prepare_assistant({'id':'x'})
        server.assistant_jobs['x']['context']['mode']='current'
        with self.assertRaises(ValueError):server.prepare_assistant({'id':'x'})
    def test_complete_control_history_required_for_scene_comparison(self):
        a=rec();b=rec('network_2',4)
        b.pop('control_history')
        self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
        b['control_history']=[dict(round=100,command='LINKCOND 4 1 50 8192')]
        self.assertEqual(ec.compare(a,b)['mode'],'descriptive')
    def test_observation_frequency_uses_recorded_sample_clock(self):
        a=rec();applied=[1,100,0,32768,0,300,0,0,0,0,1073742]
        a['snapshots'][0]['observation']=dict(applied=applied,sample_rate_hz=16000000)
        self.assertAlmostEqual(ec.compare(a,a)['left_channel_sample']['cfo_hz'],4000,places=1)

if __name__=='__main__':unittest.main()
