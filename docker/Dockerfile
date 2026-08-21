# syntax=docker/dockerfile:1.7
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Ubuntu-based image, deliberately.
#
# Ubuntu 24.04 LTS ships CPython 3.12 in its default archive, so the container
# runs the same interpreter build, glibc and OpenSSL as an Ubuntu host. That
# removes the class of "works in the container, not on the box" problems that a
# Debian-slim or Alpine base can introduce (musl vs glibc wheel selection,
# different OpenSSL minor, different libstdc++).
#
# One image serves app, scheduler, Streamlit and Jupyter; only the command
# differs.

ARG UBUNTU_VERSION=24.04
ARG UV_VERSION=0.8.17
ARG PYTHON=python3.12

# ------------------------------------------------------------------ uv bin ----
# uv arrives as its own stage rather than `COPY --from=ghcr.io/...:${UV_VERSION}`.
# BuildKit resolves stage names at parse time and does NOT substitute an ARG
# inside a COPY --from image reference — it fails with "invalid reference
# format". FROM does expand global ARGs, so pinning the version here works and
# keeps the version in one place.
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

# ---------------------------------------------------------------- builder ----
FROM ubuntu:${UBUNTU_VERSION} AS builder

ARG PYTHON
ENV DEBIAN_FRONTEND=noninteractive

# python3.12-venv is required for venv creation; it is a build-time need only.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ${PYTHON} \
        ${PYTHON}-venv \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uvbin /uv /usr/local/bin/uv

# only-system pins uv to Ubuntu's interpreter. Without this uv may download its
# own managed CPython, which would silently defeat the entire point of an
# Ubuntu base.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON=${PYTHON} \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Dependencies before source: this layer is the expensive one and must not be
# invalidated by an edit to src/.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------- runtime ----
FROM ubuntu:${UBUNTU_VERSION} AS runtime

ARG PYTHON
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        ${PYTHON} \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Ubuntu 24.04 ships a built-in 'ubuntu' account already holding UID 1000, and
# a matching 'ubuntu' group at GID 1000. Both are cleared so our user can take
# those ids, because a single-user Linux desktop is almost always 1000 and
# matching it keeps bind-mounted files writable with no host-side chown.
#
# Clearing the group is not optional: userdel does not reliably remove the
# user's primary group, and a leftover GID 1000 makes `groupadd -g 1000` fail
# with "GID already exists". The lookups are by id rather than by name so this
# still works if APP_UID/APP_GID are overridden onto some other occupied id.
ARG APP_UID=1000
ARG APP_GID=1000
RUN set -eux; \
    if getent passwd "${APP_UID}" >/dev/null; then \
        userdel -r "$(getent passwd "${APP_UID}" | cut -d: -f1)" 2>/dev/null || true; \
    fi; \
    if getent group "${APP_GID}" >/dev/null; then \
        groupdel "$(getent group "${APP_GID}" | cut -d: -f1)" 2>/dev/null || true; \
    fi; \
    groupadd -g "${APP_GID}" emeye; \
    useradd -u "${APP_UID}" -g "${APP_GID}" -m -s /bin/bash emeye

COPY --from=builder --chown=${APP_UID}:${APP_GID} /opt/venv /opt/venv
COPY --from=builder --chown=${APP_UID}:${APP_GID} /app/src /app/src
COPY --chown=${APP_UID}:${APP_GID} alembic.ini /app/alembic.ini
# scripts/ is needed in the image because `make licenses` runs the checker
# inside the container. That is the more meaningful place to run it: the
# container venv holds the runtime dependency set (--no-dev), which is exactly
# what ships.
COPY --chown=${APP_UID}:${APP_GID} scripts /app/scripts
COPY --chown=root:root docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# A fresh named volume inherits ownership from the image's directory, so
# chowning here is what makes /data writable to a non-root container user.
RUN mkdir -p /data/exports && chown -R ${APP_UID}:${APP_GID} /data

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EMEYE_DATA_DIR=/data \
    EMEYE_EXPORT_DIR=/data/exports

WORKDIR /app
USER emeye

# PID-1 signal handling is provided by compose's `init: true` rather than a
# tini package, which keeps this image dependent only on Ubuntu's main archive.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["emeye", "--help"]
