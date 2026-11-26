# Full grader image: the lite image plus the scientific Python stack.
#
# Uses a glibc (Debian) base rather than Alpine so numpy/scipy/scikit-learn/pandas/matplotlib/Pillow
# all install from prebuilt manylinux wheels. On Alpine (musl), scikit-learn has no wheel and
# compiles from source, which needs a full C/C++ toolchain (build-base) and pushes the build to
# close to an hour. On glibc no compiler is needed, so the build is a few minutes and the image no
# longer carries the toolchain.
#
# https://docs.astral.sh/uv/guides/integration/docker/#available-images
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Needed to properly handle UTF-8
ENV PYTHONIOENCODING=UTF-8
ENV LANG=C.UTF-8

WORKDIR /

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    util-linux \
    sudo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-full.txt /
ARG PACKAGE_VERSION=latest
RUN uv venv --seed && uv pip install --no-cache-dir -r requirements-full.txt && \
    uv pip install --no-cache-dir pytest-prairielearn-grader==${PACKAGE_VERSION}

# Create 'ag' user for privilege dropping in student code sandbox
RUN adduser --disabled-password --gecos "" ag
COPY --chmod=755 run.sh /run.sh

# Add serverFilesCourse to Python path
ENV PYTHONPATH=/grade/serverFilesCourse/

ENTRYPOINT [ "/run.sh" ]
