# Scrape LinkedIn Likes

This guide shows how to collect profile URLs for everyone who liked a LinkedIn post.

## Steps

1. Open the post in Chrome and click the number of likes to open the **Reactions** dialog.
2. Right‑click anywhere and choose **Inspect** to open DevTools.
3. Switch to the **Console** tab and paste the script below. It scrolls the list, waits for results to load and downloads a CSV of the profiles.
4. *(Optional)* Upload the CSV to a Dhisana AI Smart List to enrich the profiles or run a campaign.
5. *(Optional)* Use the GTM tools to push the leads to destinations like your CRM or Clay.

## Code snippet

```javascript
/**
 * Likes-scraper v2.2
 * Change: waits **15 seconds before each scroll** inside the Likes dialog.
 * All other behaviour (Show-more click, link harvesting, CSV download) unchanged.
 */

(async () => {
  /* ---------- helpers ---------- */
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const normalise = href => {
    try {
      const u = new URL(href, location.href);
      const m = u.pathname.match(/^\/in\/([^/?#]+)/i);
      return m ? `https://www.linkedin.com/in/${m[1]}` : null;
    } catch { return null; }
  };

  const extractSummary = a => a.innerText.trim().replace(/\s+/g, ' ');

  const collectLeads = store => {
    document.querySelectorAll('a[href*="/in/"]').forEach(a => {
      const url = normalise(a.getAttribute('href') || '');
      if (url && !store.has(url)) store.set(url, extractSummary(a));
    });
  };

  /* ---------- locate scrolling container ---------- */
  const container =
    document.querySelector('.social-details-reactors-tab-body .scaffold-finite-scroll') ||
    document.querySelector('.social-details-reactors-tab-body') ||
    window;

  if (container === window)
    console.warn('Dialog container not found; defaulting to window scroll.');

  /* ---------- main loop ---------- */
  const leads      = new Map();
  const MAX_SCROLL = 10;
  const SCROLL_PX  = 300;
  const WAIT_BEFORE_SCROLL_MS = 15_000;   // ← 15-second pause

  for (let i = 0; i < MAX_SCROLL; i++) {
    collectLeads(leads);

    // Look for and click “Show more results” if present
    const btn = [...container.querySelectorAll('button, a')]
                 .find(el => /show more results/i.test(el.innerText.trim()));
    if (btn) {
      btn.click();
      console.log(`Clicked “Show more results” (iteration ${i + 1}).`);
      await sleep(500);           // short pause for new nodes to render
    }

    console.log(`Waiting 15 s before scroll ${i + 1}/${MAX_SCROLL}…`);
    await sleep(WAIT_BEFORE_SCROLL_MS);

    // Perform the scroll
    if (container === window) {
      window.scrollBy(0, SCROLL_PX);
    } else if (container.scrollBy) {
      container.scrollBy(0, SCROLL_PX);
    } else {
      container.scrollTop += SCROLL_PX;
    }

    console.log(`Scrolled. Profiles collected so far: ${leads.size}`);
  }

  // final harvest
  collectLeads(leads);
  console.log(`Done. Total unique profiles: ${leads.size}`);

  /* ---------- download CSV ---------- */
  const escape = s => `"${s.replace(/"/g, '""')}"`;
  const csv = ['user_linkedin_url,lead_summary',
               ...Array.from(leads, ([url, sum]) => `${escape(url)},${escape(sum)}`)]
              .join('\n');

  const blob = new Blob([csv], { type: 'text/csv' });
  const link = Object.assign(document.createElement('a'), {
    href: URL.createObjectURL(blob),
    download: 'linkedin_likes.csv'
  });
  document.body.appendChild(link);
  link.click();
  link.remove();
})();
```

Save the downloaded CSV and continue with your workflow.
