#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Wait for the warehouse, then exec the requested command.
#
# The wait is bounded: a container that hangs forever without explaining itself
# is worse than one that fails. Set EMEYE_WAIT_FOR_DB=0 to skip entirely.
set -euo pipefail

WAIT_TIMEOUT="${EMEYE_DB_WAIT_TIMEOUT:-60}"
WAIT_ENABLED="${EMEYE_WAIT_FOR_DB:-1}"

if [[ "${WAIT_ENABLED}" == "1" ]]; then
  host="${EMEYE_POSTGRES_HOST:-postgres}"
  port="${EMEYE_POSTGRES_PORT:-5432}"
  deadline=$(( SECONDS + WAIT_TIMEOUT ))

  until python3 -c "
import socket, sys
try:
    with socket.create_connection(('${host}', ${port}), timeout=2):
        pass
except OSError:
    sys.exit(1)
" 2>/dev/null; do
    if (( SECONDS >= deadline )); then
      echo "entrypoint: timed out after ${WAIT_TIMEOUT}s waiting for postgres at ${host}:${port}" >&2
      echo "entrypoint: is the postgres service running? try 'make up' then 'make logs'" >&2
      exit 1
    fi
    sleep 1
  done
fi

exec "$@"
