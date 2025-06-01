# gtm-ai-tools

This repository provides a curated set of utilities for GTM (go-to-market) engineers to automate and streamline common workflows. It includes tools for lead discovery, enrichment and qualification, CRM data hygiene, AI-powered outreach content generation and more—helping teams accelerate pipeline generation and reduce manual effort in GTM operations.

The project is contributed to and maintained by the **[Dhisana AI](https://www.dhisana.ai)** team. Community contributions are welcome!


## Quick Start (5 minutes)

1. **Clone the repository**
   ```bash
   git clone https://github.com/dhisana-ai/gtm-ai-tools.git
   cd gtm-ai-tools
   ```
2. **Build the Docker image** (or run `task docker:build`)
   ```bash
   docker build -t gtm-ai-tools .
   ```
3. **Add your API keys** to `.env` (see [API key setup](docs/api_keys.md))
   ```bash
   OPENAI_API_KEY=...
   SERPER_API_KEY=...
   DHISANA_API_KEY=...
   HUBSPOT_API_KEY=...
   ```
4. **Launch the web app**
   ```bash
   docker run --env-file .env -p 8080:8080 gtm-ai-tools
   ```
5. Open <http://localhost:8080> and start running utilities.

## Repository structure

- `utils/` – Stand‑alone Python utilities.
- `Dockerfile` – Container image definition for running the utilities in an Azure Functions compatible environment with Playwright support.
- `requirements.txt` – Python dependencies for the utilities.
- `.env` – Environment variables consumed by the utilities.
- `app/` – Simple Flask web app launched when the Docker container starts.

## Prerequisites

- Ensure Docker is installed. See [Installing Docker](docs/install_docker.md).
- Obtain API keys and add them to `.env`. See [API key setup](docs/api_keys.md).
- Install Git and clone this repository. See [Git setup](docs/doc.md).


## Running the utilities

This project ships with a `Taskfile.yml` for simplified commands. The
[`task`](https://taskfile.dev) tool is installed inside the Docker image and can
be installed locally using the official script:

```bash
curl -sL https://taskfile.dev/install.sh | sh -s -- -b /usr/local/bin
```

Common actions:

1. Build the Docker image

   ```bash
   task docker:build
   ```

2. Update the repository

   ```bash
   task git:pull
   ```

3. Run a utility inside the container

   ```bash
   task run:command openai_sample "Hello!"
   ```

   The output of the command is saved to `output/run.log` in your working
   directory.

To keep files produced by a command, write them to `/workspace` inside the
container. The `output/` directory on your host maps to this path. For example:

```bash
task run:command linkedin_search_to_csv \
    "site:linkedin.com/in growth hacker" /workspace/results.csv -n 20
```

After the run you will find `results.csv` inside the `output/` directory.
The Taskfile also copies any files created in `output/` to `/tmp/outputs`,
creating that directory if it does not already exist. This provides a stable
location for retrieving results outside the project tree.

To use files from an arbitrary directory on your host, mount that directory when
starting the container. For example to read `/tmp/input.csv` and produce
`/tmp/output.csv`:

```bash
docker run --env-file .env -v /tmp:/tmp gtm-ai-tools \
    python -m utils.find_users_by_name_and_keywords \
    /tmp/input.csv /tmp/output.csv
```

### Running utilities locally

You can also execute any of the scripts directly on your machine without using
Docker. Invoke the module with Python and provide normal file paths. For
example:

```bash
python -m utils.find_users_by_name_and_keywords input.csv output.csv
```

## Adding new utilities

Place additional stand-alone scripts inside the `utils/` directory. After rebuilding the Docker image, start the container again and your tool will appear in the **Run a Utility** menu of the web app. Each script should include a short docstring describing its purpose.

See [Using the utilities](docs/utils_usage.md) for examples of running the sample scripts.

## OpenAI Codex CLI

The Docker image now comes with the [OpenAI Codex CLI](https://github.com/openai/codex)
installed globally via `npm`. Codex requires **Node.js 22** or later, so the image installs
Node from the official NodeSource repository. Codex helps you explore and refactor code using
natural language prompts.

1. Ensure your `OPENAI_API_KEY` is set in `.env` or exported in your shell.
2. Start the CLI in auto‑edit mode using the wrapper script:

   ```bash
   codex-auto "Explain this repo"
   ```

Codex will read files in the current directory, propose edits and apply them
automatically while still asking before running shell commands.

## Web application

Building the Docker image will also install a lightweight Flask web app located
in the `app/` directory. When the container starts without any command
arguments, the web interface launches automatically on port `8080`:

```bash
docker run -p 8080:8080 gtm-ai-tools
```

Open <http://localhost:8080> in your browser to access the app which provides a
simple interface for describing and running workflows as well as editing your
environment variables.

The homepage now offers two options:

1. **Run a Utility** – choose an available tool by its description and provide
   the command‑line parameters. If a utility requires a CSV input you can upload
   the file directly in the form. When a utility produces a CSV output a
   download link will be displayed. Plain text output is shown in the page.
2. **Build My Own Workflow** – describe a workflow in free text. The current
   implementation simply previews the text or flashes that the workflow would
   run; additional functionality can be added later.

## Utility reference

- [OpenAI Sample](docs/utils_usage.md#openai-sample) – example using the OpenAI API.
- [Search LinkedIn URLs](docs/utils_usage.md#search-linkedin-urls) – gather profile URLs from Google.
- [Find Company Info](docs/utils_usage.md#find-company-info) – locate a company's website and LinkedIn page.
- [Find User by Name and Keywords](docs/utils_usage.md#find-user-by-name-and-keywords) – look up a LinkedIn profile by name.
- [Find User by Job Title and Company](docs/utils_usage.md#find-user-by-job-title-and-company) – search by title at a company.
- [Find Users by Name and Keywords](docs/utils_usage.md#find-users-by-name-and-keywords) – process a CSV of names to find profiles.
- [Push Lead to Dhisana Webhook](docs/utils_usage.md#push-lead-to-dhisana-webhook) – send a lead record to Dhisana.
- [Push Company to Dhisana Webhook](docs/utils_usage.md#push-company-to-dhisana-webhook) – send a company record to Dhisana.
- [Get HubSpot Contact](docs/utils_usage.md#get-hubspot-contact) – retrieve a CRM contact.
- [Create HubSpot Contact](docs/utils_usage.md#create-hubspot-contact) – add a new contact if one doesn't exist.
- [Update HubSpot Contact](docs/utils_usage.md#update-hubspot-contact) – modify contact properties.
- [Add HubSpot Note](docs/utils_usage.md#add-hubspot-note) – attach a note to a contact.
- [Fetch HTML with Playwright](utils/fetch_html_playwright.py) – fetch page HTML using Playwright.
- [Extract from Webpage](utils/extract_from_webpage.py) – extract leads and companies using LLMs.

