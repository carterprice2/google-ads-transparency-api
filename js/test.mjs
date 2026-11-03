import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { GoogleAdsTransparency, TransparencyError, flatten } from './index.mjs';

const FX = JSON.parse(readFileSync(new URL('../tests/fixtures/shopify.json', import.meta.url)));
const ERR = { search: 'nosuchbrand', error: 'No advertiser named "nosuchbrand" found.' };
const fakeFetch = (items = FX, status = 'SUCCEEDED', calls = []) => async (url, init) => {
    calls.push({ url, body: init.body && JSON.parse(init.body) });
    const json = url.includes('/runs') && !url.includes('/actor-runs/') ? { data: { id: 'r1', status: 'RUNNING', defaultDatasetId: 'd1' } }
        : url.includes('/actor-runs/') ? { data: { id: 'r1', status, defaultDatasetId: 'd1' } } : items;
    return { ok: true, status: 200, json: async () => json, text: async () => '' };
};

test('search sends the actor input and returns ads', async () => {
    const calls = [];
    globalThis.fetch = fakeFetch(FX.concat(ERR), 'SUCCEEDED', calls);
    const gat = new GoogleAdsTransparency({ token: 't' });
    const ads = await gat.search(['shopify.com', 'nosuchbrand'], { region: 'US', lastDays: 30, adText: true });
    assert.equal(ads.length, 3);
    assert.deepEqual(calls[0].body, { searches: ['shopify.com', 'nosuchbrand'], region: 'US', format: 'all', platform: 'all',
        maxAdsPerSearch: 100, includeDetails: false, includeAdText: true, advertisersPerName: 1, lastDays: 30 });
    assert.equal((await gat.search('x', { includeErrors: true })).length, 4);
    const row = flatten(ads[0]);
    assert.ok(row.headline && row.videoUrl && row.regions === 'US');
});

test('failures throw', async () => {
    globalThis.fetch = fakeFetch([ERR]);
    await assert.rejects(new GoogleAdsTransparency({ token: 't' }).search('nosuchbrand'), /nosuchbrand/);
    globalThis.fetch = fakeFetch(FX, 'FAILED');
    await assert.rejects(new GoogleAdsTransparency({ token: 't' }).search('x'), TransparencyError);
    await assert.rejects(new GoogleAdsTransparency({ token: 't' }).search('x', { format: 'gif' }), TypeError);
    assert.throws(() => new GoogleAdsTransparency({ token: '' }), TransparencyError);
});
