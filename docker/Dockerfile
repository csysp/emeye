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

# ---------------------------------------------------------------- builder ----
FROM ubuntu:${UBUNTU_VERSION} AS builder

ARG PYTHON
ARG UV_VERSION
ENV DEBIAN_FRONTEND=noninteractive

# python3.12-venv is required for venv creation; it is a build-time need only.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ${PYTHON} \
        ${PYTHON}-venv \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /usr/local/bin/uv

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

# Ubuntu 24.04 ships a built-in 'ubuntu' account already holding UID 1000.
# Removing it frees UID 1000 for our own user, which matters because a
# single-user Linux desktop is almost always UID 1000 — matching it keeps
# bind-mounted files writable without any host-side chown. Override at build
# time with --build-arg APP_UID=... if the host user differs.
ARG APP_UID=1000
ARG APP_GID=1000
RUN userdel -r ubuntu 2>/dev/null || true; \
    groupadd -g ${APP_GID} emeye && \
    useradd -u ${APP_UID} -g ${APP_GID} -m -s /bin/bash emeye

COPY --from=builder --chown=${APP_UID}:${APP_GID} /opt/venv /opt/venv
COPY --from=builder --chown=${APP_UID}:${APP_GID} /app/src /app/src
COPY --chown=${APP_UID}:${APP_GID} alembic.ini /app/alembic.ini
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
