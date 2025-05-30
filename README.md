# gtm-ai-tools

This repository provides a curated set of utilities for GTM (go-to-market) engineers to automate and streamline common workflows. It includes tools for lead discovery, enrichment and qualification, CRM data hygiene, AI-powered outreach content generation and more—helping teams accelerate pipeline generation and reduce manual effort in GTM operations.

The project is contributed to and maintained by the **[Dhisana AI](https://www.dhisana.ai)** team. Community contributions are welcome!

## Repository structure

- `utils/` – Stand‑alone Python utilities.
- `Dockerfile` – Container image definition for running the utilities in an Azure Functions compatible environment with Playwright support.
- `requirements.txt` – Python dependencies for the utilities.
- `.env` – Environment variables consumed by the utilities.

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
   task run:command -- python utils/openai_sample.py "Hello!"
   ```

   The output of the command is saved to `output/run.log` in your working
   directory.

## Adding new utilities

Place additional stand‑alone scripts inside the `utils/` directory. They will be available inside the Docker image once built.

See [Using the utilities](docs/utils_usage.md) for examples of running the sample scripts.
