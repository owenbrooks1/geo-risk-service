# Design

To be completed.

## Architecture overview

## Data flow

## Component boundaries

## Key trade-offs

## Security and privacy

## Technology choices

## Likely production and cloud shape

- **Ingestion:** logins arrive on an event stream. A consumer calls the same per-login assessment function and keeps each customer's last usable location in a state store, with a stated rule for late events.
- **Storage:** DuckDB is replaced by a managed relational store for decisions and run state, and a warehouse for analysis and evaluation. Truth labels sit in a separate store that the assessment service has no access to (INV-5).
- **IP data:** a licensed IP geolocation feed, loaded as time-versioned reference data with the same validity rules as the synthetic table.
- **API:** behind the enterprise gateway, with identity from enterprise single sign-on and access checked by role.
- **Policy:** versioned config, promoted through the same pipeline as code, so every decision can be traced to the rule that made it.
