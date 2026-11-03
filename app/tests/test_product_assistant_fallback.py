"""Failure isolation: optional inference must never become hardware authority."""
import unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import product_assistant as ai

class AssistantFallback(unittest.TestCase):
    def test_unavailable_preserves_rules_and_never_executes(self):
        with patch.object(ai,'available',return_value={'available':False}):
            r=ai.answer('现在能把高度设为2000米吗？',None,{})
        self.assertFalse(r['model_used']);self.assertEqual(r['actions_executed'],0)
        self.assertEqual(r['mode'],'rules_only')
    def test_model_connection_error_isolated(self):
        with patch.object(ai,'available',return_value={'available':True,'models':['test']}),patch.object(ai.urllib.request,'urlopen',side_effect=OSError('offline')):
            r=ai.answer('请立即执行命令',None,{})
        self.assertFalse(r['model_used']);self.assertEqual(r['actions_executed'],0)
        self.assertIn('没有执行',r['answer'])
    def test_oversize_input_rejected_before_model(self):
        with patch.object(ai,'available') as model:
            with self.assertRaises(ValueError):ai.answer('q',None,{},'x'*32001)
            model.assert_not_called()

if __name__=='__main__':unittest.main()
