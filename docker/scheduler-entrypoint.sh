#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Export the EMEYE_* environment into a file cron can source, then run cron in
# the foreground. Without this, jobs run with an empty environment and fail in
# ways that look like application bugs.
set -euo pipefail

env | grep -E '^EMEYE_' | sed 's/^/export /' > /tmp/emeye-env.sh || true
chmod 0600 /tmp/emeye-env.sh

crontab /app/docker/crontab
echo "scheduler: cron installed; $(grep -cvE '^\s*(#|$)' /app/docker/crontab) job(s) scheduled" >&2

exec cron -f
