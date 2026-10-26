"""Politely downloads the two REAL approved pages (robots.txt checked) and tests the parsers on them."""
import os, json
os.environ["SCHOLAR_LIVE"] = "1"
import tracker
for s in json.load(open("sources.json")):
    try:
        html = tracker.fetch(s); path = f"fixtures/real_{s['id']}.html"
        open(path, "w", encoding="utf-8").write(html)
        items = list(tracker.ADAPTERS[s["adapter"]](html))
        print(s["id"], "saved", path, "| parsed", len(items), "notices")
        for i in items[:3]: print("   ", i["title"], "|", i["provider"], "|", i["deadline"] or "no deadline")
    except Exception as e: print(s["id"], "FAILED:", repr(e))
