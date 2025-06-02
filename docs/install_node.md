# Installing Node.js and the Codex CLI

The Codex CLI requires **Node.js 22** or newer. The steps below use the Node Version Manager (nvm) so they work on Linux or macOS.

## On Windows using WSL

1. Launch your **Ubuntu** (or other Linux) distribution.
2. Install nvm:
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
   source ~/.nvm/nvm.sh
   ```
3. Install the latest Node.js release and the Codex CLI:
   ```bash
   nvm install node
   npm install -g @openai/codex
   ```

## On Macbook

1. Install nvm:
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
   source ~/.nvm/nvm.sh
   ```
2. Install Node.js and the Codex CLI:
   ```bash
   nvm install node
   npm install -g @openai/codex
   ```

## Using the task command

You can run the following from the project root to perform the same steps automatically:

```bash
task setup:codex
```
