# Scrape Any Web Page Using ChatGPT

ChatGPT can generate quick JavaScript snippets that you paste into the Chrome console to collect links or other text from a page. After downloading the results you can enrich them with Dhisana AI.

## Example: gather commenters from a LinkedIn post

1. Open the LinkedIn post in Chrome.
2. Right‑click the page and choose **Inspect** to view the HTML.
3. Paste the prompt below into ChatGPT to generate the script.

```
Give me a standalone javascript that does the following which I can copy paste into chrome console.
This javascript
1. Finds all the linkedin urls of the format linkedin.com/in* in the page and creates a list
2. finds if there is a button with text Load more comments inside the same. Then click on the button
<button id="ember1968" class="comments-comments-list__load-more-comments-button--cr artdeco-button artdeco-button--muted artdeco-button--1 artdeco-button--tertiary ember-view"><!---->
<span class="artdeco-button__text">
    Load more comments
</span></button>
3. Do step 1 to find the linkedin urls then de-dup and add to the list. have all the linkedin user urls normalized to https://www.linkedin.com/in/<id>
4. Do step 2 & 2 max of 30 times with a delay of 30 seconds between each load. stop if there is no more load more comments found.

Take all the user_linkedin_urls aggregated so far and trigger the download of it as a csv file for download.
Give me a js i can copy paste into chrome console for above.
I am basically trying to find all users who have commented on a post.
```

4. Copy the code ChatGPT returns.
5. Open **DevTools** → **Console**, paste the code and press **Enter**.
6. A CSV with the collected profile URLs will download.
7. Upload the CSV to Dhisana AI Smart List for enrichment or outreach.

Tweak the prompt to target other selectors or elements and you can scrape nearly any page without paying for separate tools.
