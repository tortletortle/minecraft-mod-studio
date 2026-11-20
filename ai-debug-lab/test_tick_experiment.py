import unittest
from tick_experiment import run_tick_experiment,validate_steps,ExperimentFailure

class FakeServer:
    def __init__(self,overshoot=False,cleanup_fail=False):
        self.t=0;self.frozen=False;self.stdin=self;self.cmds=[];self.now=0
        self.overshoot=overshoot;self.cleanup_fail=cleanup_fail
    def poll(self):return None
    def write(self,s):
        cmd=s.strip();self.cmds.append(cmd)
        if cmd=="tick freeze":self.frozen=True
        elif cmd=="tick unfreeze":
            if not self.cleanup_fail:self.frozen=False
        elif cmd.startswith("tick step "):self.t+=int(cmd.split()[-1])+int(self.overshoot)
        else:raise AssertionError(cmd)
    def flush(self):pass
    def sleep(self,n):
        self.now+=n
        if not self.frozen:self.t+=max(1,int(n*20))
    def read(self,op):
        return ("The game is frozen" if self.frozen else "The game is running normally") if op["op"]=="ticks" else f"The game time is {self.t} tick(s)"
    def run(self,steps,approved=True):
        return run_tick_experiment(self,self.read,steps,approved_disposable=approved,clock=lambda:self.now,sleep=self.sleep)

class TickExperimentTests(unittest.TestCase):
    def test_exact_steps_and_resume(self):
        p=FakeServer();r=p.run([1,5,20])
        self.assertEqual(r["status"],"passed")
        self.assertEqual([e["delta"] for e in r["events"] if e["kind"]=="step_verified"],[1,5,20])
        self.assertEqual(r["cleanup"],"verified_running")
        self.assertFalse(p.frozen)
    def test_reject_without_approval(self):
        p=FakeServer()
        with self.assertRaises(ValueError):p.run([1],False)
        self.assertEqual(p.cmds,[])
    def test_validate_entire_plan(self):
        for steps in [[1,"stop"],[True],[0],[101],[100,100,1],[],[1]*11]:
            p=FakeServer()
            with self.assertRaises(ValueError):p.run(steps)
            self.assertEqual(p.cmds,[])
    def test_overshoot_invalid_and_resume(self):
        p=FakeServer(overshoot=True)
        with self.assertRaises(ExperimentFailure) as ctx:p.run([5])
        self.assertEqual(ctx.exception.report["status"],"invalid")
        self.assertEqual(ctx.exception.report["cleanup"],"verified_running")
        self.assertIn("tick unfreeze",p.cmds)
    def test_cleanup_failure_not_pass(self):
        p=FakeServer(cleanup_fail=True)
        with self.assertRaises(ExperimentFailure) as ctx:p.run([1])
        self.assertEqual(ctx.exception.report["cleanup"],"failed_terminate_owned_server")
    def test_initial_frozen_no_mutation(self):
        p=FakeServer();p.frozen=True
        with self.assertRaises(ExperimentFailure):p.run([1])
        self.assertEqual(p.cmds,[])

if __name__=="__main__":unittest.main()
