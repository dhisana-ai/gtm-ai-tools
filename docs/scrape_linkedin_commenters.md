# Scrape LinkedIn Commenters

This guide shows how to quickly gather profile URLs for everyone who commented on a LinkedIn post.

## Steps

1. Open the LinkedIn post in Chrome.
2. Right‑click anywhere on the page and choose **Inspect** to open DevTools.
3. Switch to the **Console** tab.
4. Copy and paste the code snippet below and press **Enter**.
5. A CSV named `linkedin_commenters.csv` will be downloaded containing the profile URLs.
6. *(Optional)* Upload the CSV to Dhisana AI Smart List to enrich the profiles and run a campaign.
7. *(Optional)* Use GTM tools to push the leads to services like Clay.

## Code snippet

```javascript
/**
 * Scrape all commenter profile URLs on a LinkedIn post.
 * – Clicks "Load more comments" (if present) up to 30 times,
 *   waiting 30 s between clicks so new comments can render.
 * – Collects every anchor that contains "/in/" in its href,
 *   normalises them to https://www.linkedin.com/in/<id>,
 *   deduplicates, and finally downloads a CSV.
 *
 * How to use:
 * 1. Open the LinkedIn post in Chrome.
 * 2. Open DevTools (F12) ▸ Console.
 * 3. Paste this whole script and press Enter.
 *    A file named **linkedin_commenters.csv** will be downloaded when done.
 */

(async () => {
  /* ---------- helpers ---------- */
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const normaliseUrl = href => {
    try {
      // Accept absolute or relative links
      const u = new URL(href, location.href);
      const m = u.pathname.match(/^\/in\/([^/?#]+)/i);
      if (!m) return null;
      return `https://www.linkedin.com/in/${m[1]}`;
    } catch (_) {
      return null;
    }
  };

  const collectUrls = () => {
    const anchors = Array.from(document.querySelectorAll('a[href*="/in/"]'));
    return anchors
      .map(a => normaliseUrl(a.getAttribute('href') || ''))
      .filter(Boolean);
  };

  const clickLoadMore = () => {
    const btn = Array.from(document.querySelectorAll('button, a')).find(el =>
      /load more comments/i.test(el.innerText.trim())
    );
    if (btn) btn.click();
    return !!btn;
  };

  /* ---------- main loop ---------- */
  const MAX_ITER = 30;       // how many times to click
  const WAIT_MS  = 30_000;   // wait after each click (30 s)

  const urls = new Set();

  for (let i = 0; i < MAX_ITER; i++) {
    // Step 1: harvest current links
    collectUrls().forEach(u => urls.add(u));
    console.log(`Iteration ${i + 1}: ${urls.size} unique URLs so far`);

    // Step 2: attempt to load more comments
    const clicked = clickLoadMore();
    if (!clicked) {
      console.log('No “Load more comments” button found — finishing early.');
      break;
    }

    // Step 3: wait for new comments to load
    console.log('Clicked “Load more comments”. Waiting 30 s…');
    await sleep(WAIT_MS);
  }

  // One final sweep just in case
  collectUrls().forEach(u => urls.add(u));
  console.log(`Finished. Total unique commenter profiles: ${urls.size}`);

  /* ---------- download CSV ---------- */
  const csv = Array.from(urls).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = 'linkedin_commenters.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  console.log('CSV download triggered ✔️');
})();
```

Save the downloaded CSV and continue with your workflow.
