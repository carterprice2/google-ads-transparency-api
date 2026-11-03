import csv, json, pathlib, pytest
import google_ads_transparency as g
from google_ads_transparency.__main__ import main

FX = json.loads((pathlib.Path(__file__).parent / "fixtures" / "shopify.json").read_text())
ERR = {"search": "nosuchbrand", "error": "No advertiser named \"nosuchbrand\" found.", "scrapedAt": "2026-11-03T00:00:00Z"}


class Fake(g.GoogleAdsTransparency):
    """Replays the Apify API: start run -> poll once -> dataset items."""
    def __init__(self, items=FX, status="SUCCEEDED"):
        super().__init__("test-token")
        self.items, self.status, self.calls = items, status, []

    def _call(self, method, path, body=None, **params):
        self.calls.append((method, path, body))
        if path.endswith("/runs"):
            return {"data": {"id": "r1", "status": "RUNNING", "defaultDatasetId": "d1"}}
        if path.startswith("/actor-runs/"):
            return {"data": {"id": "r1", "status": self.status, "defaultDatasetId": "d1"}}
        return self.items


def test_search_sends_actor_input():
    gat = Fake()
    ads = gat.search("shopify.com", region="US", format="video", last_days=30, max_ads=3, details=True, ad_text=True)
    assert gat.calls[0][1] == "/acts/seodatalab~google-ads-transparency-scraper/runs"
    assert gat.calls[0][2] == {"searches": ["shopify.com"], "region": "US", "format": "video", "platform": "all",
                               "maxAdsPerSearch": 3, "includeDetails": True, "includeAdText": True,
                               "advertisersPerName": 1, "lastDays": 30}
    assert len(ads) == 3 and ads[0]["adText"]["videoUrl"].startswith("https://www.youtube.com/")
    with pytest.raises(ValueError):
        gat.search("x", format="gif")
    with pytest.raises(ValueError):
        gat.search([])


def test_errors_dropped_with_warning_or_raised_when_all_fail():
    with pytest.warns(UserWarning, match="nosuchbrand"):
        ads = Fake(items=FX + [ERR]).search(["shopify.com", "nosuchbrand"])
    assert len(ads) == 3
    assert len(Fake(items=FX + [ERR]).search(["a", "b"], include_errors=True)) == 4
    with pytest.raises(g.TransparencyError, match="nosuchbrand"):
        Fake(items=[ERR]).search("nosuchbrand")
    with pytest.raises(g.TransparencyError, match="FAILED"):
        Fake(status="FAILED").search("x")


def test_flatten_and_cli(tmp_path, monkeypatch):
    row = g.flatten(FX[0])
    assert row["headline"] and row["landingUrl"] and row["regions"] == "US" and row["impressionsMin"] is None
    assert g.flatten({"adUrl": "u"})["headline"] is None  # ads without extras flatten too
    import google_ads_transparency.__main__ as cli
    monkeypatch.setattr(cli, "GoogleAdsTransparency", lambda: Fake())
    out = tmp_path / "ads.csv"
    assert main(["shopify.com", "--region", "US", "--ad-text", "--csv", str(out)]) == 0
    rows = list(csv.DictReader(out.open()))
    assert len(rows) == 3 and rows[0]["advertiserName"] == "Shopify Inc."


def test_to_dataframe():
    pytest.importorskip("pandas")
    df = g.to_dataframe(FX)
    assert len(df) == 3 and "headline" in df.columns
