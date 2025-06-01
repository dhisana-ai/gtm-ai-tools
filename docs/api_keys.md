# Obtaining API Keys

This project uses several APIs. Follow the steps below to generate the required keys and add them to your environment variables.

## OpenAI API Key

1. Visit [https://platform.openai.com/signup](https://platform.openai.com/signup) and sign up or log in.
2. Click your profile icon and choose **View API keys**.
3. Click **Create new secret key** and copy the value displayed.

## Serper.dev API Key

1. Visit [https://serper.dev](https://serper.dev) and create an account.
2. After verifying your email, the dashboard displays your API key.
3. Copy the key shown under **API key**.

## Dhisana API Key

1. Sign up at [https://www.dhisana.ai](https://www.dhisana.ai).
2. Select **API Credentials** from the menu.
3. Click **New API Key** and copy the value provided.

## HubSpot API Key

1. Log into your HubSpot account.
2. Navigate to **Settings** &rarr; **Integrations** &rarr; **Private Apps**.
3. Create a new private app and copy the access token shown.

## Slack Webhook URL

1. Visit <https://api.slack.com/messaging/webhooks> and create an incoming webhook.
2. Copy the webhook URL displayed.

## Adding the keys to the environment

Edit the `.env` file in the project root and set each key:

```bash
OPENAI_API_KEY=your_openai_key
SERPER_API_KEY=your_serper_key
DHISANA_API_KEY=your_dhisana_key
HUBSPOT_API_KEY=your_hubspot_key
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

Save the file. The utilities and the Codex CLI will read these variables when run.
# SMTP Credentials

To use the e-mail sending utility you also need SMTP credentials. Add these to your `.env` file:

```bash
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_password
SMTP_SENDER_EMAIL=you@example.com
```

`SMTP_PORT` should be the numeric port number for the server. The address set in
`SMTP_SENDER_EMAIL` is used as the default sender address by the utility.
