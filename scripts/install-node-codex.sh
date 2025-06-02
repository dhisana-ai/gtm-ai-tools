#!/bin/bash
# Install latest Node.js using nvm and then install the Codex CLI
set -euo pipefail

# Install nvm if not present
if ! command -v nvm >/dev/null 2>&1; then
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
  # shellcheck source=/dev/null
  source "$HOME/.nvm/nvm.sh"
else
  # shellcheck source=/dev/null
  source "$HOME/.nvm/nvm.sh"
fi

# Install and use the latest Node.js
nvm install node
nvm use node

# Install the Codex CLI globally
npm install -g @openai/codex
