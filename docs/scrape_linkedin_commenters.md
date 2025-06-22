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
 * Scrape all **commenter** profile URLs on a LinkedIn post – now with a
 * `lead_summary` column.
 *
 * • Clicks “Load more comments” (if present) up to 30 ×, waiting 30 s
 *   between clicks so new comments render.
 * • For every <a> whose href contains “/in/”, captures:
 *     – `user_linkedin_url`  → canonical https://www.linkedin.com/in/<id>
 *     – `lead_summary`       → the anchor’s full innerText (trimmed)
 * • De-duplicates by URL and downloads **linkedin_commenters.csv**
 *
 * How to use:
 *   1. Open the LinkedIn post in Chrome.
 *   2. Open DevTools ▸ Console (F12) and paste this whole script.
 */

(async () => {
  /* ---------------- helpers ---------------- */
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  /** canonicalise any LinkedIn /in/ URL */
  const normalise = href => {
    try {
      const u = new URL(href, location.href);
      const m = u.pathname.match(/^\/in\/([^/?#]+)/i);
      return m ? `https://www.linkedin.com/in/${m[1]}` : null;
    } catch { return null; }
  };

  /** harvest (url, summary) pairs currently visible */
  const collectLeads = () =>
    Array.from(document.querySelectorAll('a[href*="/in/"]'))
      .map(a => ({
        url: normalise(a.getAttribute('href') || ''),
        summary: a.innerText.trim().replace(/\s+/g, ' ')
      }))
      .filter(l => l.url);

  /** click “Load more comments” if it exists */
  const clickLoadMore = () => {
    const btn = [...document.querySelectorAll('button, a')]
      .find(el => /load more comments/i.test(el.innerText.trim()));
    if (btn) btn.click();
    return !!btn;
  };

  /* ---------------- main loop ---------------- */
  const MAX_ITER = 30;      // how many “load more” clicks max
  const WAIT_MS  = 30_000;  // wait 30 s after each click

  const leads = new Map();  // Map<url, summary>

  for (let i = 0; i < MAX_ITER; i++) {
    collectLeads().forEach(({ url, summary }) => leads.set(url, summary));
    console.log(`Iteration ${i + 1}: ${leads.size} unique URLs so far`);

    if (!clickLoadMore()) {
      console.log('No “Load more comments” button found — finishing early.');
      break;
    }

    console.log('Clicked. Waiting 30 s for new comments…');
    await sleep(WAIT_MS);
  }

  // final sweep
  collectLeads().forEach(({ url, summary }) => leads.set(url, summary));
  console.log(`Finished. Total unique commenters: ${leads.size}`);

  /* ---------------- download CSV ---------------- */
  const escape = s => `"${s.replace(/"/g, '""')}"`;
  const rows   = Array.from(leads, ([url, summary]) =>
                   `${escape(url)},${escape(summary)}`);
  const csv    = ['user_linkedin_url,lead_summary', ...rows].join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const link = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(blob),
    download: 'linkedin_commenters.csv'
  });
  document.body.appendChild(link);
  link.click();
  link.remove();

  console.log('CSV download triggered ✔️');
})();
```

Save the downloaded CSV and continue with your workflow.
