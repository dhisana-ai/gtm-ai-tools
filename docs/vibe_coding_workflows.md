# Vibe coding new workflows

This project uses the OpenAI Codex CLI to scaffold new utilities.
The CLI runs locally, outside the Docker container.

1. Install **Node.js 22+** and the CLI:
   ```bash
   npm install -g @openai/codex
   ```
2. Generate a script from the project root:
   ```bash
   task add_utility -- my_tool "describe what it should do"
   ```
3. Work on a branch, then commit and push the changes:
   ```bash
   git checkout -b my-feature
   git commit -am "Add my tool"
   git push origin my-feature
   ```
