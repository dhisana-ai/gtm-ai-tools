# gtm-ai-tools

This repository provides a curated set of utilities for GTM (go-to-market) engineers to automate and streamline common workflows. It includes tools for lead discovery, enrichment and qualification, CRM data hygiene, AI-powered outreach content generation and more—helping teams accelerate pipeline generation and reduce manual effort in GTM operations.

The project is contributed to and maintained by the **[Dhisana AI](https://www.dhisana.ai)** team. Community contributions are welcome!

## Repository structure

- `utils/` – Stand‑alone Python utilities.
- `Dockerfile` – Container image definition for running the utilities in an Azure Functions compatible environment with Playwright support.
- `requirements.txt` – Python dependencies for the utilities.
- `.env` – Environment variables consumed by the utilities.

## Running with Docker

1. Build the Docker image:

```bash
docker build -t gtm-ai-tools .
```

2. Run a utility inside the container. The example below runs `openai_sample.py` and loads environment variables from `.env`:

```bash
docker run --env-file .env gtm-ai-tools python utils/openai_sample.py "Hello!"
```

This will print the response returned from the OpenAI API using the key provided in the `.env` file.

## Adding new utilities

Place additional stand‑alone scripts inside the `utils/` directory. They will be available inside the Docker image once built.
