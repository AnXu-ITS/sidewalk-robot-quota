"""Scientific boundary checks: undefined throughput and the fixed pass threshold."""
import unittest,json,sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from sidewalk_admission import seed_pass,predict
CFG=json.loads((ROOT/'configs/admission.json').read_text(encoding='utf8'))


class ServiceChecks(unittest.TestCase):
    def test_zero_denominator_never_passes(self):
        d=pd.DataFrame({'inflow_ped':[0,10],'outflow_ped':[0,10],'mean_speed':[1.,1.],'mean_density':[.5,.5]})
        self.assertEqual(seed_pass(d,1.,CFG['service']).tolist(),[False,True])

    def test_exclusion_is_not_zero_admission(self):
        for status in ['TECHNICAL_INVALID','OUT_OF_DOMAIN_GEOMETRY']:
            self.assertEqual(predict({'q_star_status':status},'M0',[],0,CFG),(None,status))

    def test_29_of_30_boundary(self):
        d=pd.DataFrame({'inflow_ped':[10]*30,'outflow_ped':[10]*30,'mean_speed':[1.]*29+[.89],'mean_density':[.5]*30})
        self.assertEqual(int(seed_pass(d,1.,CFG['service']).sum()),29)
        d.loc[0,'inflow_ped']=0
        self.assertLess(int(seed_pass(d,1.,CFG['service']).sum()),CFG['service']['passing_seeds'])


if __name__=='__main__':unittest.main()
