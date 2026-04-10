FROM python:3.13

LABEL maintainer="agent-orchestration-core"
#LABEL version="1.0.0"

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

RUN groupadd -r appuser && useradd -r -g appuser -d /home/appuser appuser \
    && mkdir -p /home/appuser \
    && chown -R appuser:appuser /home/appuser

ENV HOME=/home/appuser

WORKDIR /app

# Install dependencies
COPY --chown=appuser:appuser ./pyproject.toml ./install.sh ./
RUN uv --version && \
    chmod +x install.sh && \
    ./install.sh

# Add application code
COPY --chown=appuser:appuser . .

RUN mkdir -p /var/log/ab-agent-router /tmp/logs/ab-agent-router /app/logs/ab-agent-router /app/scripts

COPY --chown=appuser:appuser resources/scripts/ /app/scripts/


RUN chmod +x start.sh

RUN chown -R appuser:appuser /app

USER appuser

ENV PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["./start.sh"]
