import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import current_evidence as evidence

class EvidenceIdentity(unittest.TestCase):
    def test_same_version_different_program_is_not_current(self):
        images={'bit':'a','elf':'b','init':'c'}
        self.assertFalse(evidence.matches({'version':'000d0005','image_hashes':{**images,'elf':'older'}},images))
    def test_all_three_image_hashes_required(self):
        self.assertFalse(evidence.matches({'images':{'system_wrapper.bit':'a','swarm_app.elf':'b'}},{'bit':'a','elf':'b','init':'c'}))
    def test_both_existing_receipt_naming_conventions(self):
        images={'bit':'a','elf':'b','init':'c'}
        self.assertTrue(evidence.matches({'image_hashes':images},images))
        self.assertTrue(evidence.matches({'images':{evidence.NAMES[k]:v for k,v in images.items()}},images))

if __name__=='__main__':unittest.main()
