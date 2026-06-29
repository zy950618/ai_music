FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY music_ai ./music_ai
COPY examples ./examples
COPY tools ./tools
COPY docs ./docs

RUN python -m compileall music_ai tools

EXPOSE 8787

CMD ["python", "-m", "music_ai.web", "--host", "0.0.0.0", "--port", "8787", "--workspace", "runs/web"]

