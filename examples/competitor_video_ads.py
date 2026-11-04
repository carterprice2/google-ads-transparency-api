from google_ads_transparency import GoogleAdsTransparency, to_dataframe

ads = GoogleAdsTransparency().search(
    "hubspot.com", region="US", format="video", last_days=30, max_ads=5, ad_text=True)
print(to_dataframe(ads)[["daysShown", "headline", "landingUrl"]].to_string())
