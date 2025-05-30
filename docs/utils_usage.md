# Using the Utilities

This page provides usage instructions for the sample scripts included in the `utils/` folder.

## OpenAI Sample

`openai_sample.py` sends a prompt to OpenAI and prints the response returned from the API. The script requires the `OPENAI_API_KEY` environment variable.

Run it from the project root (or inside the container) with a prompt:

```bash
python utils/openai_sample.py "Hello!"
```

Or with Docker after building the image:

```bash
docker run --env-file .env gtm-ai-tools python utils/openai_sample.py "Hello!"
```

The script prints the text from the `responses.create` call.

## Search LinkedIn URLs

`linkedin_search_to_csv.py` queries Google through SerpAPI to find LinkedIn profile URLs and writes them to a CSV file. It requires the `SERAPI_API_KEY` environment variable.

Example usage fetching 20 results:

```bash
python utils/linkedin_search_to_csv.py "site:linkedin.com/in growth hacker" results.csv -n 20
```

Or inside Docker:

```bash
docker run --env-file .env gtm-ai-tools \
    python utils/linkedin_search_to_csv.py \
    "site:linkedin.com/in growth hacker" results.csv -n 20
```

This creates `results.csv` containing a `user_linkedin_url` column.
