# Geospatial Risk Intelligence Service

A small, locally runnable service that checks each login for impossible travel, using only the IP location evidence available at that moment. It explains every decision and abstains when the evidence is weak. Built with Python, DuckDB and FastAPI, on synthetic data only.

**Status:** in progress. Run instructions will be added as the slice is built.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and `make`.

```sh
uv sync
```

## Verify

```sh
make verify
```

Runs lint, format and lock checks, then the tests. The same command runs in CI.

## Links

- Working method and hard rules: [`AGENTS.md`](AGENTS.md)
- Evidence pack: [`evidence/`](evidence/)
- Component status: [`docs/components.md`](docs/components.md)
