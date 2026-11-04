// Google Ads Transparency Center API for JavaScript/Node 18+ (no dependencies). Calls the hosted scraper
// seodatalab/google-ads-transparency-scraper on Apify, which handles requests, retries and proxies.
const API = 'https://api.apify.com/v2';
export const FORMATS = ['all', 'text', 'image', 'video'];
export const PLATFORMS = ['all', 'search', 'youtube', 'shopping', 'maps', 'play'];

export class TransparencyError extends Error {}

export class GoogleAdsTransparency {
    constructor({ token = globalThis.process?.env?.APIFY_TOKEN, actor = 'seodatalab~google-ads-transparency-scraper', timeoutMs = 1_800_000 } = {}) {
        if (!token) throw new TransparencyError('No Apify token. Create a free account at https://apify.com?fpr=fi898m and pass { token } or set APIFY_TOKEN.');
        Object.assign(this, { token, actor, timeoutMs });
    }

    async #call(method, path, body, params = {}) {
        const qs = new URLSearchParams(params).toString();
        const r = await fetch(`${API}${path}${qs ? `?${qs}` : ''}`, {
            method, body: body === undefined ? undefined : JSON.stringify(body),
            headers: { authorization: `Bearer ${this.token}`, 'content-type': 'application/json' },
        });
        if (!r.ok) throw new TransparencyError(`Apify API ${r.status}: ${(await r.text()).slice(0, 300)}`);
        return r.json();
    }

    /**
     * Ads for one or more searches: domains (nike.com), advertiser names, advertiser IDs (AR...) or Ads Transparency URLs.
     * Failed searches are dropped (they cost nothing) unless includeErrors is true; throws only if every search failed.
     */
    async search(searches, { region = 'anywhere', format = 'all', platform = 'all', lastDays, startDate, endDate, maxAds = 100,
        details = false, adText = false, advertisersPerName = 1, includeErrors = false, ...extra } = {}) {
        const list = Array.isArray(searches) ? searches : [searches];
        if (!list.length) throw new TypeError('Pass at least one domain, advertiser name, advertiser ID or URL.');
        if (!FORMATS.includes(format)) throw new TypeError(`format must be one of ${FORMATS}`);
        if (!PLATFORMS.includes(platform)) throw new TypeError(`platform must be one of ${PLATFORMS}`);
        const input = { searches: list, region, format, platform, maxAdsPerSearch: maxAds, includeDetails: details, includeAdText: adText, advertisersPerName, ...extra };
        if (lastDays) input.lastDays = lastDays;
        if (startDate) input.startDate = startDate;
        if (endDate) input.endDate = endDate;

        let run = (await this.#call('POST', `/acts/${this.actor}/runs`, input)).data;
        const deadline = Date.now() + this.timeoutMs;
        while (run.status === 'READY' || run.status === 'RUNNING') {
            if (Date.now() > deadline) throw new TransparencyError(`Run ${run.id} still running after ${this.timeoutMs / 1000}s.`);
            run = (await this.#call('GET', `/actor-runs/${run.id}`, undefined, { waitForFinish: 60 })).data;
        }
        if (run.status !== 'SUCCEEDED') throw new TransparencyError(`Run ${run.id} ended with status ${run.status}. Log: https://console.apify.com/view/runs/${run.id}`);
        const rows = await this.#call('GET', `/datasets/${run.defaultDatasetId}/items`, undefined, { clean: 'true', format: 'json' });
        const errors = rows.filter((r) => r.error);
        if (errors.length && errors.length === rows.length) throw new TransparencyError(errors.map((r) => `${r.search}: ${r.error}`).join('; '));
        return includeErrors ? rows : rows.filter((r) => !r.error);
    }
}

/** One flat row per ad, handy for CSV or a spreadsheet. */
export function flatten(ad) {
    const t = ad.adText ?? {};
    const d = ad.details ?? {};
    const imp = d.impressions ?? {};
    return {
        search: ad.search, advertiserName: ad.advertiserName, advertiserId: ad.advertiserId, creativeId: ad.creativeId,
        format: ad.format, domain: ad.domain, firstShown: ad.firstShown, lastShown: ad.lastShown, daysShown: ad.daysShown,
        headline: t.headline ?? null, longHeadline: t.longHeadline ?? null, description: t.description ?? null,
        displayUrl: t.displayUrl ?? null, landingUrl: t.landingUrl ?? null, videoUrl: t.videoUrl ?? null, videoDuration: t.videoDuration ?? null,
        regions: (d.regions ?? []).map((r) => r.region).join(',') || null,
        impressionsMin: imp.min ?? null, impressionsMax: imp.max ?? null, imageUrl: ad.imageUrl ?? null, adUrl: ad.adUrl,
    };
}
