ARG BASE_IMAGE=python:3.11-slim-bullseye

FROM ${BASE_IMAGE} AS builder

RUN python3 -m pip install --no-cache -U uv

COPY ./src/requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=PIP_INDEX_URL \
    export PIP_INDEX_URL=$(cat /run/secrets/PIP_INDEX_URL) \
    export UV_INDEX_URL=$(cat /run/secrets/PIP_INDEX_URL) \
    && uv pip install --no-cache --system --python python --target=/app/libs -r /tmp/requirements.txt

COPY ./src/ /app/src
COPY ./VERSION /app/src/VERSION
COPY ./README.md /app/src/README.md
RUN uv pip install --no-cache --system --python python --target=/app/libs /app/src

FROM ${BASE_IMAGE}

COPY --from=builder /app/libs /root/.local/lib/python3.11/site-packages

COPY ./config/config.yaml /config/config.yaml

ENV PATH=/root/.local/bin:$PATH

WORKDIR /app/

RUN find / -xdev -perm -4000 -o -perm -2000 -type f -exec chmod a-s {} \; || true

CMD ["python", "-m", "redup_service_example.service", "/config/config.yaml"]