# Pushing Leads to Dhisana

After running any tool you can send the results directly to Dhisana for enrichment and automated outreach.

1. In Dhisana create a **Smart List** and choose the **Webhook** option.
2. Copy the webhook URL and generate an API key from the Dhisana dashboard.
3. Open the app **Settings** page and set `DHISANA_WEBHOOK_URL` and `DHISANA_API_KEY` with the values you copied.
4. Run any utility. When results contain LinkedIn profile URLs a **Push Output to Dhisana AI Webhook** button will appear. Click it to push the leads to Dhisana.

The platform will qualify and research each lead, score them and automatically add them to the correct outreach campaign.

## Input Modes

You can push leads to Dhisana regardless of how you supplied data to a utility:

1. **Single Input** – When running a tool with a single input value the output panel includes the button if any LinkedIn URLs are detected.
2. **CSV Input** – Upload a CSV file and run a utility. After it finishes you can push all LinkedIn URLs from the resulting CSV.
3. **Use Previous Output** – Switch the input mode to *Use Previous Output* to feed an earlier CSV back into another tool. The push button is still available so you can send those results to Dhisana as well.
