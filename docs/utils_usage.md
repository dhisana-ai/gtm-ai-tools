# Using the Utilities

This page provides usage instructions for the sample scripts included in the `utils/` folder.

## OpenAI Sample

`openai_sample.py` sends a prompt to OpenAI and prints the response returned from the API. The script requires the `OPENAI_API_KEY` environment variable.

Run it with the Taskfile:

```bash
task run:command -- openai_sample "Hello!"
```

The script prints the text from the `responses.create` call.

## Search LinkedIn URLs

`linkedin_search_to_csv.py` queries Google through Serper.dev to find LinkedIn profile URLs and writes them to a CSV file. It requires the `SERPER_API_KEY` environment variable.

Example usage fetching 20 results:

```bash
task run:command -- linkedin_search_to_csv \
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
task run:command -- find_company_info "Dhisana" -l "San Francisco"
```

The script prints a JSON object containing `company_website`, `company_domain` and `linkedin_url`.

## Find User by Name and Keywords

`find_a_user_by_name_and_keywords.py` searches Google via Serper.dev for a person's LinkedIn profile. Provide the person's full name and optional additional keywords. The script outputs a JSON object containing the full name, the LinkedIn profile URL and the search keywords used.

Run it with a name and keywords:

```bash
task run:command -- find_a_user_by_name_and_keywords \
    "Jane Doe" "growth marketing"
```

The script prints the resulting JSON to stdout.

## Find Users by Name and Keywords

`find_users_by_name_and_keywords.py` reads a CSV containing `full_name` and
`search_keywords` columns. For each row it looks up the person's LinkedIn profile
using Google search through Serper.dev and writes the results to a new CSV file.

Run it with an input and output file:

```bash
task run:command -- find_users_by_name_and_keywords \
    /workspace/input.csv /workspace/output.csv
```

The resulting CSV contains `full_name`, `user_linkedin_url` and
`search_keywords` for each entry.
