# Using the Utilities

This page provides usage instructions for the sample scripts included in the `utils/` folder.

## OpenAI Sample

`openai_sample.py` sends a prompt to OpenAI and prints the response returned from the API. The script requires the `OPENAI_API_KEY` environment variable.

Run it from the project root (or inside the container) with a prompt:

```bash
python utils/openai_sample.py "Hello!"
```

Or using the Taskfile after building the image:

```bash
task run:command -- python utils/openai_sample.py "Hello!"
```

The script prints the text from the `responses.create` call.

## Search LinkedIn URLs

`linkedin_search_to_csv.py` queries Google through Serper.dev to find LinkedIn profile URLs and writes them to a CSV file. It requires the `SERPER_API_KEY` environment variable.

Example usage fetching 20 results:

```bash
python utils/linkedin_search_to_csv.py "site:linkedin.com/in growth hacker" results.csv -n 20
```

Or using the Taskfile with a mounted volume to access the output file locally:

```bash
task run:command -- python utils/linkedin_search_to_csv.py \
    "site:linkedin.com/in growth hacker" /workspace/results.csv -n 20
```
The Taskfile mounts the `output/` directory from your host to `/workspace`
inside the container. By writing to `/workspace/results.csv` you will find the
file at `output/results.csv` locally. Inspect it with `cat output/results.csv`.
After the command finishes, everything in `output/` is also copied to
`/tmp/outputs` for convenience.
## Find Company Info

`find_company_info.py` looks up a company's website, primary domain and LinkedIn page using Google search. It uses the `SERPER_API_KEY` environment variable for Google queries.

Run it with the company name and optional location:

```bash
task run:command -- python utils/find_company_info.py "Dhisana" -l "San Francisco"
```

The script prints a JSON object containing `company_website`, `company_domain` and `linkedin_url`.
