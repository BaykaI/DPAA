# -*- coding: utf-8 -*-
import json, collections, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "..", "drc.json"), encoding="utf-8"))
v = d["violations"]; u = d.get("unconnected_items", [])
print("DRC: нарушений", len(v), "неподключённых", len(u))
print(collections.Counter(x["type"] + "/" + x.get("severity", "") for x in v).most_common())
for x in v[:25]:
    if x.get("severity") == "error":
        it = x["items"]; p = it[0]["pos"] if it else {}
        print("  %-22s (%5.1f,%5.1f) %s | %s" % (x["type"], p.get("x", 0), p.get("y", 0), it[0]["description"][:50] if it else "", it[1]["description"][:50] if len(it) > 1 else ""))
for x in u[:20]:
    it = x["items"]; p = it[0]["pos"] if it else {}
    print("  UNCONNECTED (%5.1f,%5.1f) %s | %s" % (p.get("x", 0), p.get("y", 0), it[0]["description"][:50], it[1]["description"][:50] if len(it) > 1 else ""))
e = os.path.join(HERE, "..", "erc.json")
if os.path.exists(e):
    d = json.load(open(e, encoding="utf-8"))
    vs = [x for s in d["sheets"] for x in s["violations"]]
    print("ERC:", len(vs), collections.Counter(x["type"] + "/" + x.get("severity", "") for x in vs).most_common())
    for x in vs[:10]:
        if x.get("severity") == "error":
            print("  ", x["type"], x.get("description", "")[:80], [i["description"][:40] for i in x["items"]])
