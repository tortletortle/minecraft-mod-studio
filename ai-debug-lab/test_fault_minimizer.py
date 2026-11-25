import unittest
from fault_minimizer import Model,minimize

GRAPH={"fabric":[],"lib":["fabric"],"alpha":["lib"],"beta":["fabric"],"noise":["fabric"],"extra":[]}
TARGET="fixture:target"

def oracle_factory(fn):
    calls=[]
    def oracle(config,seed,repeat,trial_id):
        calls.append((config,seed,repeat,trial_id))
        result=fn(set(config),seed,repeat)
        if result=="target":outcome,fp="observed",TARGET
        elif result=="other":outcome,fp="observed","fixture:other"
        elif result=="invalid":outcome,fp="invalid",None
        else:outcome,fp="absent",None
        return {"trial_id":trial_id,"outcome":outcome,"fingerprint":fp,"evidence_id":trial_id}
    return oracle,calls

def run(fn,**kwargs):
    oracle,calls=oracle_factory(fn)
    report=minimize(GRAPH,["fabric"],oracle,fingerprint=TARGET,**kwargs)
    return report,calls

class MinimizerTests(unittest.TestCase):
    def test_dependency_reverse_closure(self):
        m=Model(GRAPH,["fabric"])
        self.assertEqual(m.remove(m.all,["lib"]),frozenset({"fabric","beta","noise","extra"}))
        self.assertIsNone(m.remove(m.all,["fabric"]))
    def test_pair_with_dependency(self):
        r,calls=run(lambda c,s,i:"target" if {"alpha","beta"}<=c else "absent")
        self.assertEqual(r["status"],"candidate_confirmed")
        self.assertEqual(set(r["candidate"]),{"fabric","lib","alpha","beta"})
        self.assertTrue(all(x["result"]=="not_observed" for x in r["final_checks"]))
        self.assertEqual(len({i for _,_,_,i in calls}),len(calls))
        self.assertTrue(all("lib" in c for c,_,_,_ in calls if "alpha" in c))
    def test_intermittent_baseline(self):
        r,_=run(lambda c,s,i:"target" if i==0 else "absent")
        self.assertEqual(r["reason"],"baseline_intermittent")
        self.assertEqual(r["status"],"inconclusive")
    def test_other_crash_not_target(self):
        r,_=run(lambda c,s,i:"target" if {"alpha","beta"}<=c else "other")
        self.assertEqual(r["reason"],"negative_control_not_clean")
    def test_unresolved_removal_not_certified(self):
        def scenario(c,s,i):
            if {"alpha","beta"}<=c:return "target"
            if not {"alpha","beta"}&c:return "absent"
            return "invalid"
        r,_=run(scenario)
        self.assertEqual(r["status"],"inconclusive")
        self.assertEqual(r["reason"],"removal_confirmation_inconclusive")
    def test_budget_strict(self):
        r,calls=run(lambda c,s,i:"target" if "alpha" in c else "absent",budget=7)
        self.assertEqual(len(calls),6)
        self.assertEqual(r["reason"],"trial_budget_exhausted")
    def test_invalid_graph_and_seeds(self):
        with self.assertRaises(ValueError):Model({"a":["missing"]})
        with self.assertRaises(ValueError):run(lambda *a:"absent",seeds=[42,42])
    def test_cyclic_required_dependencies(self):
        m=Model({"a":["b"],"b":["a"],"core":[]},["core"])
        self.assertEqual(m.remove(m.all,["a"]),frozenset({"core"}))
    def test_receipt_reuse_invalid(self):
        def oracle(c,s,i,t):return {"trial_id":t,"outcome":"observed","fingerprint":TARGET,"evidence_id":"same"}
        r=minimize(GRAPH,["fabric"],oracle,fingerprint=TARGET)
        self.assertEqual(r["reason"],"baseline_unresolved")
    def test_nonmonotonic_controls(self):
        r,_=run(lambda c,s,i:"target" if "alpha" in c or c=={"fabric"} else "absent")
        self.assertEqual(r["reason"],"negative_control_not_clean")
    def test_fresh_confirmation_detects_drift(self):
        counts={}
        def scenario(c,s,i):
            key=(tuple(sorted(c)),s,i)
            counts[key]=counts.get(key,0)+1
            return "target" if {"alpha","beta"}<=c and counts[key]==1 else "absent"
        r,_=run(scenario)
        self.assertEqual(r["reason"],"fresh_confirmation_inconclusive")

if __name__=="__main__":unittest.main()
