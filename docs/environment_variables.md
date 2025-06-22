# Environment Variables

The utilities and sample web app rely on a number of environment variables. Add these settings to your `.env` file before running the Docker container locally or deploying on Fly.io. Most API keys can be generated following the steps in [API key setup](api_keys.md).

| Variable | Purpose & how to obtain |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API key used for all language model prompts. Create one from your [OpenAI dashboard](https://platform.openai.com/account/api-keys). |
| `OPENAI_MODEL_NAME` | Optional. Override the default OpenAI model (defaults to `gpt-4.1`). |
| `MODEL_TO_GENERATE_UTILITY` | Optional. Model name used when generating utilities from the web interface (defaults to `o3`). |
| `SERPER_API_KEY` | API key for Serper.dev used by search utilities. Obtain it from [serper.dev](https://serper.dev). |
| `DHISANA_API_KEY` | API key for Dhisana AI. Generate it on the **API Credentials** page in your Dhisana account. |
| `DHISANA_WEBHOOK_URL` | Webhook endpoint for Dhisana Smart Lists. Copy it when creating the webhook. |
| `DHISANA_COMPANY_INPUT_URL` | Webhook URL for sending company data to Dhisana. |
| `APOLLO_API_KEY` | Apollo.io API key for people and company lookups. Create one in your Apollo dashboard. |
| `HUBSPOT_API_KEY` | HubSpot private app token used by HubSpot utilities. Generate a private app under **Settings &rarr; Integrations &rarr; Private Apps**. |
| `CLAY_API_KEY` | Clay API key for pushing rows to Clay tables. Find it under **Settings &rarr; API Keys** in Clay. |
| `CLAY_WEBHOOK_URL` | Webhook URL for a Clay table. Copy it from the table's **Webhook** tab. |
| `FINDYMAIL_API_KEY` | Findymail API key for e-mail and phone lookups. Obtain it from [findymail.com](https://findymail.com). |
| `ZERO_BOUNCE_API_KEY` | ZeroBounce API key used for e-mail validation. Create one from your ZeroBounce dashboard. |
| `SALESFORCE_INSTANCE_URL` | Base URL for your Salesforce organization (e.g. `https://example.my.salesforce.com`). |
| `SALESFORCE_ACCESS_TOKEN` | OAuth access token for Salesforce API calls. Generated from your connected app. |
| `SALESFORCE_USERNAME` | Username used for Salesforce SOAP login in the query utility. |
| `SALESFORCE_PASSWORD` | Password used with `SALESFORCE_USERNAME` for login in the query utility. |
| `SALESFORCE_SECURITY_TOKEN` | Security token issued by Salesforce for SOAP API logins. |
| `SALESFORCE_DOMAIN` | Domain for Salesforce SOAP login (defaults to `login`). |
| `SMTP_SERVER` | Hostname of your SMTP server for sending e-mail. |
| `SMTP_PORT` | Port number of your SMTP server. |
| `SMTP_USERNAME` | Username for SMTP authentication. |
| `SMTP_PASSWORD` | Password for SMTP authentication. |
| `SMTP_SENDER_EMAIL` | Default `From` address when sending e-mail. |
| `PROXY_URL` | Optional Brightdata or other proxy URL used by the Playwright scraper. |
| `TWO_CAPTCHA_API_KEY` | API key for 2Captcha when running the scraper in stealth mode. |
| `SLACK_WEBHOOK_URL` | Incoming webhook URL for posting messages to Slack. |
| `MCP_SERVER_LABEL` | Optional label for the MCP server used by `mcp_tool_sample.py`. |
| `MCP_SERVER_URL` | MCP server base URL. |
| `MCP_API_KEY_HEADER_NAME` | HTTP header name for the MCP API key. |
| `MCP_API_KEY_HEADER_VALUE` | Value of the MCP API key header. |
| `HEADLESS` | Set to `false` to launch a visible browser for Playwright utilities. |
| `APP_USERNAME` | Username for logging into the sample web app (defaults to `user`). |
| `APP_PASSWORD` | Password for the web app login. |

