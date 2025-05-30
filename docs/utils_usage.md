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

Or inside Docker with volume mount to access the output file locally:

```bash
docker run --env-file .env -v $(pwd):/workspace gtm-ai-tools \
    python utils/linkedin_search_to_csv.py \
    "site:linkedin.com/in growth hacker" /workspace/results.csv -n 20
```

This creates `results.csv` in your current directory containing a `user_linkedin_url` column that you can access directly on your host machine.
## Find Company Info

`find_company_info.py` looks up a company's website, primary domain and LinkedIn page using Google search. It uses the `SERAPI_API_KEY` environment variable for Google queries.

Run it with the company name and optional location:

```bash
python utils/find_company_info.py "Dhisana" -l "San Francisco"
```

The script prints a JSON object containing `company_website`, `company_domain` and `linkedin_url`.
