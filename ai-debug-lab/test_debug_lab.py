import json
import socket
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from debug_lab import compile_read, query, packet, read_packet, scan_mods, trial_summary, collect

class LabTest(unittest.TestCase):
    def test_commands(self):
        self.assertEqual(compile_read({"op":"ticks"}), "tick query")
        self.assertEqual(compile_read({"op":"block_nbt","dimension":"minecraft:overworld","pos":[1,2,3]}),
                         "execute in minecraft:overworld run data get block 1 2 3")
        self.assertEqual(compile_read({"op":"block_matches","dimension":"minecraft:the_nether","pos":[1,2,3],"block":"mod:machine"}),
                         "execute in minecraft:the_nether run execute if block 1 2 3 mod:machine")
        self.assertIn("data get entity", compile_read({"op":"entity_nbt","dimension":"minecraft:overworld","uuid":"12345678-1234-1234-1234-123456789abc"}))
        for op in [{"op":"stop"},{"op":"players","command":"kill @e"},
                   {"op":"block_nbt","dimension":"minecraft:overworld run stop","pos":[1,2,3]},
                   {"op":"block_nbt","dimension":"minecraft:overworld","pos":[True,2,3]},
                   {"op":"entity_nbt","dimension":"minecraft:overworld","uuid":"@e"},
                   {"op":"block_matches","dimension":"minecraft:overworld","pos":[1,2,3],"block":"stone run stop"}]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                compile_read(op)

    def run_mock(self, mode):
        listener = socket.socket()
        listener.bind(("127.0.0.1",0))
        listener.listen()
        listener.settimeout(3)
        port = listener.getsockname()[1]
        errors = []
        def server():
            try:
                with listener:
                    c,_ = listener.accept()
                    with c:
                        self.assertEqual(read_packet(c,time.monotonic()+2),(1,3,b"test"))
                        if mode == "auth":
                            c.sendall(packet(-1,2,b""))
                            return
                        c.sendall(packet(1,2,b""))
                        self.assertEqual(read_packet(c,time.monotonic()+2),(2,2,b"tick query"))
                        if mode == "timeout":
                            time.sleep(0.3)
                            return
                        if mode == "badframe":
                            c.sendall(b"\x01\x00\x00\x00")
                            return
                        if mode == "missing":
                            c.sendall(packet(3,0,b"Unknown request c8"))
                            return
                        raw = "机器".encode()
                        first = packet(2,0,raw[:2])
                        for i in range(0,len(first),3):
                            c.sendall(first[i:i+3])
                        self.assertEqual(read_packet(c,time.monotonic()+2),(3,200,b""))
                        wire = packet(2,0,raw[2:])+packet(3,0,b"Unknown request c8")
                        for i in range(0,len(wire),3):
                            c.sendall(wire[i:i+3])
            except Exception as e:
                errors.append(e)
        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        try:
            if mode == "ok":
                self.assertEqual(query({"op":"ticks"},"test",port,2),"机器")
            else:
                expected={"auth":PermissionError,"timeout":TimeoutError,"badframe":ValueError,"missing":ValueError}[mode]
                with self.assertRaises(expected):
                    query({"op":"ticks"},"test",port,0.15 if mode=="timeout" else 2)
        finally:
            thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])

    def test_fragmented_response(self): self.run_mock("ok")
    def test_bad_auth(self): self.run_mock("auth")
    def test_timeout(self): self.run_mock("timeout")
    def test_bad_frame(self): self.run_mock("badframe")
    def test_missing_response(self): self.run_mock("missing")

    def test_plan_all_validated_before_connect(self):
        with self.assertRaises(ValueError):
            collect([{"op":"ticks"},{"op":"stop"}],"test")

    def test_scan(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            for name in ("a.jar","b.jar"):
                with zipfile.ZipFile(root/name,"w") as z:
                    z.writestr("fabric.mod.json",json.dumps({"id":"a","version":"1","depends":{"base":"*"}}))
            (root/"bad.jar").write_bytes(b"not a jar")
            with zipfile.ZipFile(root/"other.jar","w") as z:
                z.writestr("META-INF/mods.toml","x")
            with zipfile.ZipFile(root/"large.jar","w") as z:
                z.writestr("fabric.mod.json","x"*270000)
            report=scan_mods(root)
            self.assertEqual(report["duplicate_declared_ids"],{"a":["a.jar","b.jar"]})
            self.assertEqual(len(report["jars"][0]["sha256"]),64)
            self.assertEqual([r["status"] for r in report["jars"]],
                             ["fabric_manifest","fabric_manifest","unreadable","unreadable","non_fabric_or_unknown"])

    def test_trial_labels(self):
        rows=[]
        for condition,outcomes in [("A",["observed","not_observed","observed"]),("B",["not_observed"]*3),("C",["observed"]*3),("D",["observed","invalid"])]:
            for i,outcome in enumerate(outcomes):
                rows.append(dict(trial_id=condition+str(i),condition=condition,seed=i,outcome=outcome))
        labels={k:v["label"] for k,v in trial_summary(rows)["conditions"].items()}
        self.assertEqual(labels,{"A":"intermittent","B":"not_observed_in_trials","C":"observed_all","D":"insufficient"})
        with self.assertRaises(ValueError): trial_summary(rows+[rows[0]])

if __name__=="__main__": unittest.main()
