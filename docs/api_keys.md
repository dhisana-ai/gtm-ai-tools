# Obtaining API Keys

This project uses several APIs. Follow the steps below to generate the required keys and add them to your environment variables.

## OpenAI API Key

1. Visit [https://platform.openai.com/signup](https://platform.openai.com/signup) and sign up or log in.
2. Click your profile icon and choose **View API keys**.
3. Click **Create new secret key** and copy the value displayed.

## SERAPI API Key

1. Go to [https://serpapi.com](https://serpapi.com) and create an account.
2. After verifying your email, the dashboard displays your API key.
3. Copy the key shown under **API key**.

## Dhisana API Key

1. Sign up at [https://www.dhisana.ai](https://www.dhisana.ai).
2. Select **API Credentials** from the menu.
3. Click **New API Key** and copy the value provided.

## Adding the keys to the environment

Edit the `.env` file in the project root and set each key:

```bash
OPENAI_API_KEY=your_openai_key
SERAPI_API_KEY=your_serapi_key
DHISANA_API_KEY=your_dhisana_key
```

Save the file. The utilities will read these variables when run.
