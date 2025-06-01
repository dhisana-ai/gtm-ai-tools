# Vibe coding new workflows

This project uses the OpenAI Codex CLI to scaffold new utilities. The CLI is not bundled in the Docker image so you must install it locally.

```bash
npm install -g @openai/codex
```

Once installed you can run the helper task to generate a script:

```bash
task add_utility my_tool "describe what it should do"
```

Codex will modify files in the repository. It's recommended to work on a separate branch:

```bash
git checkout -b my-feature
task add_utility my_tool "..."
git commit -am "Add my tool"
git push origin my-feature
```
