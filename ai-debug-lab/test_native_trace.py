import copy
import unittest
from native_trace import Trace, capture

SESSION="12345678-1234-1234-1234-123456789abc"

def snapshot(tick=100,block="minecraft:chest",visible=True,stamp="2026-11-20T00:00:00Z"):
    b={"dimension":"minecraft:overworld","x":0,"y":80,"z":0,"status":"observed" if visible else "chunk_not_loaded"}
    if visible:
        b["id"]=block
        if block=="minecraft:chest":b["block_entity_type"]="minecraft:chest"
    return {"schema":1,"session":SESSION,"tick_callbacks":tick,"window_callbacks":100,"window_elapsed_ms":5000,"at":stamp,"block":b}

class TraceTests(unittest.TestCase):
    def test_changes(self):
        t=Trace(SESSION);t.append(snapshot());t.append(snapshot(200,"mod:machine"))
        self.assertEqual(t.events[0]["type"],"observed_block_changed")
        self.assertEqual(t.events[0]["after"]["id"],"mod:machine")
        self.assertEqual(t.report("deadline")["records"][1]["tick"],200)
    def test_visibility_is_not_removal(self):
        t=Trace(SESSION);t.append(snapshot());t.append(snapshot(200,visible=False));t.append(snapshot(300,"minecraft:air"))
        self.assertEqual([e["type"] for e in t.events],["visibility_changed","visibility_changed"])
        self.assertNotIn("id",t.records[1]["block"])
    def test_gap_and_duplicates(self):
        t=Trace(SESSION);self.assertTrue(t.append(snapshot()));self.assertFalse(t.append(snapshot()))
        t.append(snapshot(400))
        self.assertEqual(t.duplicates,1)
        self.assertEqual(t.events[0]["unobserved_callbacks"],200)
    def test_conflict_and_reversal(self):
        t=Trace(SESSION);t.append(snapshot(200))
        for bad in [snapshot(100),snapshot(200,"mod:other")]:
            with self.assertRaises(ValueError):t.append(bad)
        self.assertEqual(len(t.records),1)
    def test_session_and_coordinates(self):
        t=Trace(SESSION);t.append(snapshot())
        bad=snapshot(200);bad["session"]="wrong"
        with self.assertRaises(ValueError):t.append(bad)
        bad=snapshot(200);bad["block"]["x"]=1
        with self.assertRaises(ValueError):t.append(bad)
    def test_invalid_measurements(self):
        for key,value in [("window_elapsed_ms",float("nan")),("tick_callbacks",True),("at","invalid")]:
            bad=snapshot();bad[key]=value
            with self.assertRaises(ValueError):Trace(SESSION).append(bad)
    def test_clock_regression(self):
        t=Trace(SESSION);t.append(snapshot());t.append(snapshot(200,stamp="2026-11-19T23:59:59Z"))
        self.assertEqual(t.events[0]["type"],"wall_clock_regression")
    def test_capture_bounded_and_missing(self):
        class FakeBridge:
            def __init__(self):self.rows=iter([None,snapshot(),snapshot(),snapshot(200)])
            def dispatch(self,req):
                v=next(self.rows)
                return {"ok":False} if v is None else {"ok":True,"result":{"data":v}}
        now=[0]
        def sleep(s):now[0]+=s
        report=capture(FakeBridge(),SESSION,10,1,2,lambda:now[0],sleep)
        self.assertEqual(report["stop_reason"],"record_limit")
        self.assertEqual(report["read_errors"],1)
        self.assertEqual(report["duplicate_polls"],1)
        self.assertEqual(len(report["records"]),2)

if __name__=="__main__":unittest.main()
