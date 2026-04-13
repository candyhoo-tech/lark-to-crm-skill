#!/bin/bash
# Entry point for launchd / cron. Runs auto_sync.py with the right env.
set -e
cd "$(dirname "$0")/.."
/usr/bin/env python3 scripts/auto_sync.py
