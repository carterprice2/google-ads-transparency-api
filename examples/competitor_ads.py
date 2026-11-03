"""Which ads are my competitors running this week, and which have run the longest?

    export APIFY_TOKEN=...
    python examples/competitor_ads.py hubspot.com salesforce.com pipedrive.com
"""
import sys
from google_ads_transparency import GoogleAdsTransparency, flatten

competitors = sys.argv[1:] or ["hubspot.com", "salesforce.com"]
ads = GoogleAdsTransparency().search(competitors, region="US", last_days=7, max_ads=200, ad_text=True)

by_company = {}
for ad in ads:
    by_company.setdefault(ad["search"], []).append(flatten(ad))
for company, rows in by_company.items():
    rows.sort(key=lambda r: r["daysShown"] or 0, reverse=True)
    print(f"\n{company}: {len(rows)} ads shown in the last 7 days. Longest-running:")
    for r in rows[:5]:
        print(f"  {r['daysShown']:>4} days  {r['format']:<5}  {r['headline'] or '(image ad)'}  -> {r['landingUrl'] or r['adUrl']}")
