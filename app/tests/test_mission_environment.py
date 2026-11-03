import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from assistant_workflow_facts import extend

class SceneFacts(unittest.TestCase):
    def test_configuration_not_sensor(self):
        r=extend('天气地形如何？',{'round':100,'config':{'environment':5,'weather':7}}, {}, [])
        s=next(x for x in r if x['id']=='scene_brief')
        self.assertIn('山地、大雪',s['advice']);self.assertIn('不是无人机实测',s['advice'])
        self.assertFalse(s['evidence']['terrain_affects_physics']);self.assertIsNone(s['action'])
    def test_continuous_scene_changes(self):
        def scene(round):return next(x for x in extend('环境',{'round':round,'config':{'environment':0,'weather':0}},{},[]) if x['id']=='scene_brief')['evidence']['environment']
        self.assertEqual([scene(x) for x in (0,3000,6000)],[1,3,4])
    def test_no_observation_no_invented_report(self):
        self.assertEqual(extend('天气地形',None,{},[]),[])
if __name__=='__main__':unittest.main()
