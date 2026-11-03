"""Command line: python -m google_ads_transparency nike.com --region US --last-days 30 --ad-text --csv nike_ads.csv"""
from __future__ import annotations

import argparse
import csv
import json
import sys

from . import FORMATS, PLATFORMS, GoogleAdsTransparency, flatten


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="google_ads_transparency",
                                description="Download a company's Google ads from the Ads Transparency Center.")
    p.add_argument("searches", nargs="+", help="domains (nike.com), advertiser names, advertiser IDs (AR...) or URLs")
    p.add_argument("--region", default="anywhere", help="2-letter country code, default: anywhere")
    p.add_argument("--format", default="all", choices=FORMATS)
    p.add_argument("--platform", default="all", choices=PLATFORMS)
    p.add_argument("--last-days", type=int)
    p.add_argument("--max-ads", type=int, default=100, help="per search; 0 = all")
    p.add_argument("--details", action="store_true", help="add countries and impressions")
    p.add_argument("--ad-text", action="store_true", help="add headline, description, landing page, video link")
    p.add_argument("--csv", metavar="FILE", help="write a CSV instead of JSON lines on stdout")
    a = p.parse_args(argv)

    ads = GoogleAdsTransparency().search(a.searches, region=a.region, format=a.format, platform=a.platform,
                                         last_days=a.last_days, max_ads=a.max_ads, details=a.details, ad_text=a.ad_text)
    if a.csv:
        rows = [flatten(ad) for ad in ads]
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["search"])
            w.writeheader()
            w.writerows(rows)
        print(f"{len(rows)} ads -> {a.csv}", file=sys.stderr)
    else:
        for ad in ads:
            print(json.dumps(ad, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
