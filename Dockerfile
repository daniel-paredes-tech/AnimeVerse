# The AnimeVerse application (the `animeverse` command) as a container image.
# The same image runs every job: `migrate`, `import` and, later, a web server.
#
#   docker compose run --rm migrate
#   docker compose run --rm import
#
# Settings come from environment variables (see .env.example), never from files
# in the image, so the image holds no credentials.

# --- Stage 1: build and install the package --------------------------------------
FROM python:3.14.10-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

# --- Stage 2: the runtime image, without build tools or source checkout ----------
FROM python:3.14.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Logs go straight to stdout, where Docker (and later a cloud log service) collects them.
COPY --from=build /install /usr/local
# Never run as root inside the container.
RUN useradd --create-home --uid 10001 animeverse
USER animeverse
WORKDIR /home/animeverse
ENTRYPOINT ["animeverse"]
CMD ["--help"]
