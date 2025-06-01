# Using the Utilities

This page provides usage instructions for the sample scripts included in the `utils/` folder.

## OpenAI Sample

`openai_sample.py` sends a prompt to OpenAI and prints the response returned from the API. The script requires the `OPENAI_API_KEY` environment variable.

Run it with the Taskfile:

```bash
task run:command -- openai_sample "Hello!"
```

The script prints the text from the `responses.create` call.

## MCP Tool Sample

`mcp_tool_sample.py` sends a prompt to OpenAI using an MCP server. It requires `OPENAI_API_KEY` along with `MCP_SERVER_URL`, `MCP_API_KEY_HEADER_NAME` and `MCP_API_KEY_HEADER_VALUE`. Optionally set `MCP_SERVER_LABEL`.

Run it with:

```bash
task run:command -- mcp_tool_sample "Ping"
```


## Search LinkedIn URLs

`linkedin_search_to_csv.py` queries Google through Serper.dev to find LinkedIn profile URLs and writes them to a CSV file. It requires the `SERPER_API_KEY` environment variable.
All LinkedIn URLs in the output are normalized to the `https://www.linkedin.com/in/<id>` format.

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
The LinkedIn URL returned is normalized to the `https://www.linkedin.com/company/<id>` form.

Run it with the company name and optional location:

```bash
task run:command -- find_company_info "Dhisana" -l "San Francisco"
```

The script prints a JSON object containing `company_website`, `company_domain` and `linkedin_url`.

## Find User by Name and Keywords

`find_a_user_by_name_and_keywords.py` searches Google via Serper.dev for a person's LinkedIn profile. Provide the person's full name and optional additional keywords. The script outputs a JSON object containing the full name, the LinkedIn profile URL and the search keywords used.
The profile URL is normalized to the `https://www.linkedin.com/in/<id>` format.

Run it with a name and keywords:

```bash
task run:command -- find_a_user_by_name_and_keywords \
    "Jane Doe" "growth marketing"
```

The script prints the resulting JSON to stdout.

## Find User by Job Title and Company

`find_user_by_job_title.py` searches Google via Serper.dev for a LinkedIn profile
matching a specific job title at a company. Provide the job title, the company
name and optional extra keywords. The returned profile URL is normalized to the
`https://www.linkedin.com/in/<id>` format.

Run it with a title, company and keywords:

```bash
task run:command -- find_user_by_job_title \
    "CEO" "Costco" retail
```

The script prints the resulting JSON to stdout.

## Find Users by Name and Keywords

`find_users_by_name_and_keywords.py` reads a CSV containing `full_name` and
`search_keywords` columns. For each row it looks up the person's LinkedIn profile
using Google search through Serper.dev and writes the results to a new CSV file.
All profile URLs in the output are normalized to the `https://www.linkedin.com/in/<id>` form.

Run it with an input and output file. When using the Docker based `task` command
the paths should point inside the container (the local `output/` directory is
mounted at `/workspace`):

```bash
task run:command -- find_users_by_name_and_keywords \
    /workspace/input.csv /workspace/output.csv
```
If you want to pass paths that are outside the project directory, mount the
directory when invoking Docker and reference the files by that path inside the
container:

```bash
task run:command_local_mapping -- /tmp find_users_by_name_and_keywords \
    /tmp/input.csv /tmp/output.csv
```

The resulting CSV contains `full_name`, `user_linkedin_url` and
`search_keywords` for each entry.

## Push Lead to Dhisana Webhook

`push_lead_to_dhisana_webhook.py` sends a lead's details to a Dhisana webhook endpoint. Provide the full name and optionally the LinkedIn URL, email address, tags, and notes. The script uses the `DHISANA_API_KEY` environment variable for authentication. The webhook URL is read from `DHISANA_WEBHOOK_URL` or can be supplied with `--webhook_url`.

Example usage:

```bash
task run:command -- push_lead_to_dhisana_webhook \
    "Jane Doe" --linkedin_url https://www.linkedin.com/in/janedoe \
    --email jane@example.com --tags prospect --notes "Met at conference"
```

## Push Company to Dhisana Webhook

`push_company_to_dhisana_webhook.py` sends an organization's details to a
Dhisana webhook. Provide the organization name and optionally the primary
domain, LinkedIn URL, tags and notes. The script uses the
`DHISANA_API_KEY` environment variable for authentication. The webhook URL is
read from `DHISANA_COMPANY_INPUT_URL` or can be supplied with `--webhook_url`.

Example usage:

```bash
task run:command -- push_company_to_dhisana_webhook \
    "Acme Corp" --primary_domain acme.com \
    --linkedin_url https://www.linkedin.com/company/acme \
    --tags prospect --notes "From event"
```

## HubSpot Contact Utilities

The following scripts interact with HubSpot's CRM using the `HUBSPOT_API_KEY` environment variable.

### Get HubSpot Contact

`hubspot_get_contact.py` fetches a contact by ID, email address or LinkedIn URL.

```bash
task run:command -- hubspot_get_contact --email user@example.com
```

### Create HubSpot Contact

`hubspot_create_contact.py` checks if a contact with the given email or LinkedIn URL exists and creates one if not.

```bash
task run:command -- hubspot_create_contact --email user@example.com --first_name Jane
```

### Update HubSpot Contact

`hubspot_update_contact.py` updates known fields for a contact ID. Provide `key=value` pairs to set properties.

```bash
task run:command -- hubspot_update_contact --id 1234 firstname=Jane phone=555-1234
```

### Add HubSpot Note

`hubspot_add_note.py` attaches a note to an existing contact by ID.

```bash
task run:command -- hubspot_add_note --id 1234 --note "Followed up via email"
```

## OpenAI Codex CLI

The Docker image includes the Codex CLI for conversational code edits. Once your
`OPENAI_API_KEY` is set, start it in auto-edit mode with:

```bash
codex-auto "Explain this repo"
```

Codex proposes edits and applies them to files in the repository while still
prompting before executing shell commands.
