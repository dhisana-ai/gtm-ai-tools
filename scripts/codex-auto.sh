#!/bin/bash
# Wrapper to run OpenAI Codex CLI in fully automated edit mode
codex -q --approval-mode full-auto --auto-edit "$@"
