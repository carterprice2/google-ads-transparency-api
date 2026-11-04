"""Google Ads Transparency Center API for Python.

Get every ad a company runs on Google (Search, YouTube, Shopping, Maps, Play) from the public Ads Transparency
Center, with optional ad copy (headline, description, landing page, YouTube video) and countries/impressions.

Google has no API for the Transparency Center. This client calls a hosted scraper on Apify
(seodatalab/google-ads-transparency-scraper) that handles requests, retries and proxies.
You need a free Apify account and an API token.

    from google_ads_transparency import GoogleAdsTransparency
    gat = GoogleAdsTransparency()                  # reads APIFY_TOKEN from the environment
    ads = gat.search("nike.com", region="US", last_days=30, ad_text=True)
    for ad in ads:
        print(ad["format"], ad["lastShown"], (ad.get("adText") or {}).get("headline"))
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from typing import Any, Iterable

__version__ = "0.1.0"
__all__ = ["GoogleAdsTransparency", "TransparencyError", "flatten", "to_dataframe"]

ACTOR_ID = "seodatalab~google-ads-transparency-scraper"
API = "https://api.apify.com/v2"
FORMATS = ("all", "text", "image", "video")
PLATFORMS = ("all", "search", "youtube", "shopping", "maps", "play")


class TransparencyError(RuntimeError):
    """The run failed, or none of the searches returned ads."""


class GoogleAdsTransparency:
    """Thin client for the hosted Google Ads Transparency scraper. Standard library only."""

    def __init__(self, token: str | None = None, *, actor: str = ACTOR_ID, timeout: int = 1800,
                 user_agent: str = f"google-ads-transparency-python/{__version__}"):
        self.token = token or os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
        if not self.token:
            raise TransparencyError("No Apify token. Create a free account at https://apify.com?fpr=fi898m, copy the token from "
                                    "Settings > API & Integrations, and set APIFY_TOKEN or pass token=...")
        self.actor = actor
        self.timeout = timeout
        self.user_agent = user_agent

    # ---------- HTTP ----------
    def _call(self, method: str, path: str, body: Any = None, **params: Any) -> Any:
        url = f"{API}{path}?{urllib.parse.urlencode(params)}" if params else f"{API}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            raise TransparencyError(f"Apify API {e.code}: {e.read().decode(errors='replace')[:300]}") from None

    # ---------- core ----------
    def search(self, searches: Iterable[str] | str, *, region: str = "anywhere", format: str = "all",
               platform: str = "all", last_days: int | None = None, start_date: str | None = None,
               end_date: str | None = None, max_ads: int = 100, details: bool = False, ad_text: bool = False,
               advertisers_per_name: int = 1, include_errors: bool = False, **extra: Any) -> list[dict]:
        """Return ads for one or more searches.

        searches: website domains (nike.com), advertiser names (Shopify), advertiser IDs (AR...) or Ads
            Transparency Center URLs. Many searches in one call are cheaper and faster than many calls.
        region: 2-letter country code (US, GB, DE...) or "anywhere".
        format: "all", "text", "image" or "video". platform: "all", "search", "youtube", "shopping", "maps", "play".
        last_days: only ads shown in the last N days. Or start_date / end_date as "YYYY-MM-DD".
        max_ads: per search; 0 = all ads (big advertisers can have 100,000+).
        details: add every country the ad ran in, with impression ranges where Google publishes them (mainly the EU).
        ad_text: add headline, description, landing page and YouTube video link.
        include_errors: also return rows for searches that failed (they have an "error" key and cost nothing).
            By default they're dropped with a warning, and a TransparencyError is raised only if every search failed.
        """
        items = [searches] if isinstance(searches, str) else list(searches)
        if not items:
            raise ValueError("Pass at least one domain, advertiser name, advertiser ID or URL.")
        if format not in FORMATS:
            raise ValueError(f"format must be one of {FORMATS}")
        if platform not in PLATFORMS:
            raise ValueError(f"platform must be one of {PLATFORMS}")
        payload: dict[str, Any] = {"searches": items, "region": region, "format": format, "platform": platform,
                                   "maxAdsPerSearch": int(max_ads), "includeDetails": bool(details),
                                   "includeAdText": bool(ad_text), "advertisersPerName": int(advertisers_per_name)}
        if last_days:
            payload["lastDays"] = int(last_days)
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date
        payload.update(extra)

        rows = self._run(payload)
        errors = [r for r in rows if r.get("error")]
        if errors and len(errors) == len(rows):
            raise TransparencyError("; ".join(f"{r.get('search')}: {r['error']}" for r in errors))
        if errors and not include_errors:
            warnings.warn("Some searches failed (not charged): " +
                          "; ".join(f"{r.get('search')}: {r['error']}" for r in errors), stacklevel=2)
            rows = [r for r in rows if not r.get("error")]
        return rows

    def _run(self, payload: dict) -> list[dict]:
        run = self._call("POST", f"/acts/{self.actor}/runs", payload)["data"]
        deadline = time.time() + self.timeout
        while run["status"] in ("READY", "RUNNING"):
            if time.time() > deadline:
                raise TransparencyError(f"Run {run['id']} still running after {self.timeout}s. "
                                        f"Results so far: https://console.apify.com/view/runs/{run['id']}")
            run = self._call("GET", f"/actor-runs/{run['id']}", waitForFinish=60)["data"]
        if run["status"] != "SUCCEEDED":
            raise TransparencyError(f"Run {run['id']} ended with status {run['status']}. "
                                    f"Log: https://console.apify.com/view/runs/{run['id']}")
        return self._call("GET", f"/datasets/{run['defaultDatasetId']}/items", clean="true", format="json")


def flatten(ad: dict) -> dict:
    """One flat row per ad, handy for CSV or a spreadsheet."""
    t = ad.get("adText") or {}
    d = ad.get("details") or {}
    imp = d.get("impressions") or {}
    return {
        "search": ad.get("search"), "advertiserName": ad.get("advertiserName"), "advertiserId": ad.get("advertiserId"),
        "creativeId": ad.get("creativeId"), "format": ad.get("format"), "domain": ad.get("domain"),
        "firstShown": ad.get("firstShown"), "lastShown": ad.get("lastShown"), "daysShown": ad.get("daysShown"),
        "headline": t.get("headline"), "longHeadline": t.get("longHeadline"), "description": t.get("description"),
        "displayUrl": t.get("displayUrl"), "landingUrl": t.get("landingUrl"), "videoUrl": t.get("videoUrl"),
        "videoDuration": t.get("videoDuration"),
        "regions": ",".join(r["region"] for r in d.get("regions") or []) or None,
        "impressionsMin": imp.get("min"), "impressionsMax": imp.get("max"),
        "imageUrl": ad.get("imageUrl"), "adUrl": ad.get("adUrl"),
    }


def to_dataframe(ads: list[dict]):
    """pandas DataFrame of flattened ads (pip install pandas)."""
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover
        raise TransparencyError("to_dataframe needs pandas: pip install pandas") from None
    return pd.DataFrame([flatten(a) for a in ads])
