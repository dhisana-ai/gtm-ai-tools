# Using the Utilities

This page provides usage instructions for the sample scripts included in the `utils/` folder.

## Call OpenAI LLM

`call_openai_llm.py` sends a prompt to OpenAI and prints the response returned from the API. The script requires the `OPENAI_API_KEY` environment variable. The model defaults to `gpt-4.1` but can be overridden with `OPENAI_MODEL_NAME`.

Run it with the Taskfile:

```bash
task run:command -- call_openai_llm "Hello!"
```

The script prints the text from the `responses.create` call.

When running the tool on a CSV file through the web interface, provide a
prompt in addition to the uploaded file. The prompt is concatenated with each
row from the CSV and the responses are written to a new `llm_output` column in
the output file.

## MCP Tool Sample

`mcp_tool_sample.py` sends a prompt to OpenAI using an MCP server. It requires `OPENAI_API_KEY` along with `MCP_SERVER_URL`, `MCP_API_KEY_HEADER_NAME` and `MCP_API_KEY_HEADER_VALUE`. Optionally set `MCP_SERVER_LABEL`. The OpenAI model can also be set with `OPENAI_MODEL_NAME`.

Run it with:

```bash
task run:command -- mcp_tool_sample "Ping"
```


## Search LinkedIn URLs

`linkedin_search_to_csv.py` queries Google through Serper.dev to find LinkedIn profile URLs and extracts basic lead details from the search snippets. The results are written to a CSV file and require the `SERPER_API_KEY` environment variable.
All LinkedIn URLs in the output are normalized to the `https://www.linkedin.com/in/<id>` format and each row includes the parsed lead information.

Example usage fetching 20 results:

```bash
task run:command -- linkedin_search_to_csv \
    "site:linkedin.com/in growth hacker" /workspace/results.csv -n 20
```
The Taskfile mounts the `output/` directory from your host to `/workspace`
inside the container. By writing to `/workspace/results.csv` you will find the
file at `output/results.csv` locally. Inspect it with `cat output/results.csv`.
After the command finishes, everything in `output/` is also copied to
`/data/outputs` for convenience.

## Find Company Info

`find_company_info.py` looks up a company's website, primary domain and LinkedIn page using Google search. It uses the `SERPER_API_KEY` environment variable for Google queries. The LinkedIn URL returned is normalized to the `https://www.linkedin.com/company/<id>` form.

Provide an organization name, LinkedIn URL or website:

```bash
task run:command -- find_company_info --organization_name "Dhisana" --location "San Francisco"
```

The script prints JSON with `organization_name`, `organization_website`, `primary_domain_of_organization` and `organization_linkedin_url`.

You can also upload a CSV containing an `organization_name`, `organization_linkedin_url`
or `organization_website` column to look up multiple companies at once. The processed
results will be written to a CSV file for download in the web interface.

## Find User by Name and Keywords

`find_a_user_by_name_and_keywords.py` searches Google via Serper.dev for a person's LinkedIn profile. Provide the person's full name and optional additional keywords. The script outputs a JSON object with lead details parsed from the search results, including the LinkedIn profile URL.
The profile URL is normalized to the `https://www.linkedin.com/in/<id>` format.

Run it with a name and keywords:

```bash
task run:command -- find_a_user_by_name_and_keywords \
    "Jane Doe" "growth marketing"
```

The script prints the resulting JSON to stdout.

## Find User by Job Title and Organization

`find_user_by_job_title.py` searches Google via Serper.dev for a LinkedIn profile
matching a specific job title at an organization. Provide the job title, the
organization name and optional extra keywords. The returned profile URL is normalized to the
`https://www.linkedin.com/in/<id>` format.

Run it with a title, organization and keywords:

```bash
task run:command -- find_user_by_job_title \
    "CEO" "Costco" retail
```

The script prints the resulting JSON to stdout.

## Find Users by Name and Keywords

`find_users_by_name_and_keywords.py` reads a CSV containing `full_name` and
`search_keywords` columns. For each row it looks up the person's LinkedIn profile
using Google search through Serper.dev. The resulting CSV contains lead details
extracted from the search results (name, title, location, followers, summary) and
the normalized `user_linkedin_url`.

Run it with an input and output file. When using the Docker based `task` command
the paths should point inside the container (the local `output/` directory is
mounted at `/workspace`):

```bash
task run:command -- find_users_by_name_and_keywords \
    /workspace/input.csv /workspace/output.csv
```
If you want to pass paths that are outside the project directory, mount the
directory when invoking Docker and reference the files by that path inside the
container. For example, map a local directory to `/data`:

```bash
docker run --env-file .env -v /tmp/dhisana_gtm_tools:/data gtm-ai-tools \
    python -m utils.find_users_by_name_and_keywords \
    /data/input.csv /data/output.csv
```

The resulting CSV includes columns for the parsed lead details
(`first_name`, `last_name`, `job_title`, `linkedin_follower_count`, `lead_location`,
`summary_about_lead`) alongside the normalized `user_linkedin_url` and
`search_keywords`.

## Find Email and Phone

`find_contact_with_findymail.py` queries the Findymail API for a person's
e-mail address and phone number. Provide a LinkedIn profile URL when
available, otherwise supply the person's full name and
`primary_domain_of_organization`. Set the `FINDYMAIL_API_KEY` environment
variable before running the script.

Run it with a name and domain or with a LinkedIn URL:

```bash
# using name and company domain
task run:command -- find_contact_with_findymail "Jane Doe" example.com
# or using a LinkedIn profile
task run:command -- find_contact_with_findymail "Jane Doe" --linkedin_url https://linkedin.com/in/janedoe
```

The script prints a JSON object containing `email`, `phone` and the raw
`contact_info` returned by Findymail.

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

## Push to Clay Table

`push_to_clay_table.py` sends arbitrary data to a Clay table webhook. Provide
`key=value` pairs to build the payload. The script uses the `CLAY_API_KEY`
environment variable for authentication. The webhook URL is read from
`CLAY_WEBHOOK_URL` or can be supplied with `--webhook_url`.

Example usage:

```bash
task run:command -- push_to_clay_table name=Jane email=jane@example.com
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

## Salesforce Contact Utilities

The following scripts use `SALESFORCE_INSTANCE_URL` and `SALESFORCE_ACCESS_TOKEN` to interact with Salesforce CRM.

### Get Salesforce Contact

`salesforce_get_contact.py` fetches a contact by ID or email address.

```bash
task run:command -- salesforce_get_contact --email user@example.com
```

### Create Salesforce Contact

`salesforce_create_contact.py` checks if a contact with the given email exists and creates one if not.

```bash
task run:command -- salesforce_create_contact --email user@example.com --first_name Jane
```

### Update Salesforce Contact

`salesforce_update_contact.py` updates fields for a contact ID. Provide `key=value` pairs to set properties.

```bash
task run:command -- salesforce_update_contact --id 003xx phone=555-1234
```

### Add Salesforce Note

`salesforce_add_note.py` attaches a note to an existing contact by ID.

```bash
task run:command -- salesforce_add_note --id 003xx --note "Followed up"
```

### Send Email via SMTP

`send_email_smtp.py` sends a message using SMTP credentials from the environment. Provide the recipient address and optional subject, body and sender details.

```bash
task run:command -- send_email_smtp recipient@example.com --subject "Hi" --body "Hello"
```

### Send Slack Message

`send_slack_message.py` posts a message to Slack using a webhook URL. Set `SLACK_WEBHOOK_URL` in the environment or pass `--webhook`.

```bash
task run:command -- send_slack_message "Deployment finished"
```

### Generate Email Copy

`generate_email.py` produces a subject and body for a lead using OpenAI. Pass the lead data as JSON with `--lead` or provide a CSV via `--csv` and `--output_csv`. The `OPENAI_API_KEY` environment variable must be set.

```bash
task run:command -- generate_email --lead '{"full_name": "John Doe"}' \
    --email_generation_instructions "Write a short intro email"
```

## Generate Image with OpenAI

`generate_image.py` creates an image from a text prompt. If you supply an `--image-url` the script sends the image along with the prompt to the OpenAI responses API for editing instead of calling the legacy `images.edit` endpoint. It requires the `OPENAI_API_KEY` environment variable.

```bash
task run:command -- generate_image "an astronaut riding a horse"
```

You can achieve the same using the OpenAI Python SDK directly:

```python
from openai import OpenAI
import base64

client = OpenAI()

response = client.responses.create(
    model="gpt-4.1-mini",
    input="Generate an image of gray tabby cat hugging an otter with an orange scarf",
    tools=[{"type": "image_generation"}],
)

image_data = [
    output.result
    for output in response.output
    if output.type == "image_generation_call"
]

if image_data:
    image_base64 = image_data[0]
    with open("otter.png", "wb") as f:
        f.write(base64.b64decode(image_base64))
```

Or edit an existing image:

```bash
task run:command -- generate_image "add a beach background" --image-url http://example.com/photo.png
```

Example using the SDK with a source image:

```python
from openai import OpenAI
import base64

client = OpenAI()

prompt = """Generate a photorealistic image of a gift basket on a white background \
labeled 'Relax & Unwind' with a ribbon and handwriting-like font, \
containing all the items in the reference pictures."""

base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
    model="gpt-4.1",
    input=[
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{base64_image1}"},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{base64_image2}"},
                {"type": "input_image", "file_id": file_id1},
                {"type": "input_image", "file_id": file_id2},
            ],
        }
    ],
    tools=[{"type": "image_generation"}],
)

image_generation_calls = [
    output
    for output in response.output
    if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
    image_base64 = image_data[0]
    with open("gift-basket.png", "wb") as f:
        f.write(base64.b64decode(image_base64))
else:
    print(response.output.content)
```

## Extract Companies from Image

`extract_companies_from_image.py` detects company logos in an image URL and looks
up each organization's website, primary domain and LinkedIn page. It requires
the `OPENAI_API_KEY` and `SERPER_API_KEY` environment variables.

```bash
task run:command -- extract_companies_from_image http://example.com/logo.png
```
## Crawls a website and extract the content from a website to answer some basic questions

`get_website_information.py` scrapes company website and uses an LLM to answer the questions about the website. It requires
the `OPENAI_API_KEY` in the environment variables.

```bash
task run:command -- get_website_information http://example.com/ "what is the main color of the website?"
```

## Extract Leads From Website

`extract_from_webpage.py` scrapes a page with Playwright and uses an LLM to
parse leads or organizations from the text. Provide the starting URL and use
`--lead` or `--leads` to control how many leads are returned. You can run custom
JavaScript on the initial page load, on each page load and for pagination by
supplying natural language instructions with `--initial_actions`,
`--page_actions` and `--pagination_actions`. Parsing behaviour can be tweaked
with `--parse_instructions`. Use `--max_pages` to limit how many pages are
navigated. The previous `--next_page_selector` and `--max_next_pages` options
still work as a fallback.
Pass `--show_ux` to launch a visible browser window and wait 30 seconds on each page.

You can also pass a CSV file with a `website_url` column using the `--csv`
option. Each website in the file is processed and the aggregated results are
written to the path given with `--output_csv`.

If `--output_csv` is not supplied, the utility now prints the CSV data to
standard output instead of JSON.

```bash
task run:command -- extract_from_webpage --leads https://example.com/team \
    --output_csv /workspace/output.csv
```

The path supplied with `--output_csv` is created inside the container. Since the
local `output/` directory maps to `/workspace`, the file will be available at
`output/output.csv` on your host system. In the web interface you can switch to
**Use Previous Output** and feed this CSV into another tool such as **Enrich
Lead With Apollo.io**.


## OpenAI Codex CLI

Install the Codex CLI locally to generate new utilities with natural language prompts.
Install **Node.js 22+** first (see [install_node.md](install_node.md)) or simply run:

```bash
task setup:codex
```

This installs the latest Node.js via `nvm` and the Codex CLI.

You can then invoke it through the `task add_utility` command, which runs Codex
quietly with automatic approval:

```bash
task add_utility -- search_vp_sales "search for VP of sales and push to Dhisana Webhook"
```
