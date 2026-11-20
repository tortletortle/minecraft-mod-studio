# V0.4 native observation timeline (first slice)

Run the native probe in a disposable test instance. Obtain its session UUID from the server log (MMS_DEBUG_SESSION). From repository root:

```sh
python ai-debug-lab/native_trace.py --workspace /path/to/game --session SESSION_UUID --seconds 30 > timeline.json
```

Reads only the chosen session via the existing IDE bridge; no RCON or writes required. Polls at one second by default, keeps at most 120 distinct compact snapshots, records duplicates, missing reads, tick gaps, visibility changes, observed block ID/type changes, and clock regressions. Refuses conflicting snapshots, out-of-order ticks and session/target changes. No arbitrary log text or full registry copies in the timeline. A polling deadline does not guarantee an individual filesystem operation completes on time.

This is sampled state differencing, not a method tracer, profiler, energy-network observer or causal conflict detector. No inference of a removal when a chunk unloads. An event may occur and disappear between samples. Unit fixtures are synthetic; use actual production-JAR acceptance separately. Next: validate trace against scripted real block changes, measure probe overhead vs disabled baseline, add opt-in per-mod adapter contracts for machine energy/items, and bridge to the Studio UI only after visual design approval.
