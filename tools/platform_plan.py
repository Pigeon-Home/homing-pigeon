# Agent-Stamp: 30000f1a-3b4c-4d5e-8f6a-7b8c9d0e1f2a
import json, os, sys
legs = json.load(open(".github/platform-legs.json"))
full = os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch")
out = []
for job, entries in legs.items():
    chosen = [e for e in entries if full or e.get("tier") == "core"]
    out.append("%s=%s" % (job, json.dumps({"include": chosen})))
    out.append("%s_count=%d" % (job, len(chosen)))
with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
    fh.write("\n".join(out) + "\n")
print("tier:", "full" if full else "core", {j: len([e for e in v if full or e.get("tier")=="core"]) for j, v in legs.items()})
