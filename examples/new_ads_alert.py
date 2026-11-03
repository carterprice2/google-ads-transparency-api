"""Print ads that weren't there last time. Run it daily (cron, GitHub Actions...).

    python examples/new_ads_alert.py nike.com
"""
import json, pathlib, sys
from google_ads_transparency import GoogleAdsTransparency

domain = sys.argv[1] if len(sys.argv) > 1 else "nike.com"
seen_file = pathlib.Path(f".seen-{domain}.json")
seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()

ads = GoogleAdsTransparency().search(domain, last_days=2, max_ads=0, ad_text=True)
new = [a for a in ads if a["creativeId"] not in seen]
for a in new:
    print(a["format"], a["firstShown"][:10], (a.get("adText") or {}).get("headline") or "", a["adUrl"])
print(f"{len(new)} new ads for {domain}")
seen_file.write_text(json.dumps(sorted(seen | {a["creativeId"] for a in ads})))
