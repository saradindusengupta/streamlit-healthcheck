# -*- coding: utf-8 -*-
"""
Streamlit Healthcheck provides lightweight, extensible utilities to run automated
health checks, expose health endpoints, and collect basic metrics for Streamlit
applications. It is designed to be CI/CD-friendly and to support reliable,
observable delivery pipelines.

Key features
- Run synchronous or async health checks with timeouts and recovery hints
- Register custom checks (liveness, readiness, dependency checks)
- Expose HTTP/Streamlit endpoints for machine-readable and human-readable status
- Emit structured metrics/events suitable for scraping or CI validation
- Simple integration helpers for common backends (Redis, Postgres, external APIs)

Quickstart
----------

1) Install:

```bash
pip install streamlit_healthcheck
```

2) Basic usage:

>>> from streamlit_healthcheck import healthcheck
>>> report = healthcheck.run_all(timeout=5)
>>> if not report.ok:
>>>      # handle degraded state (log, alert, fail pipeline)
>>>      print(report.summary)

API (common surface)
-------------------

- healthcheck.run_all(timeout: float = 5) -> HealthReport
  Runs all registered checks and returns a HealthReport object with:
     - ok: bool
     - summary: str
     - details: dict
     - duration: float

- healthcheck.register(name: str, fn: Callable, *, critical: bool = False)
  Register a custom check function. Critical checks mark the whole service unhealthy.

- healthcheck.serve(endpoint: str = "/health", host: str = "0.0.0.0", port: int = 8000)
  Expose a simple HTTP endpoint (or embed in Streamlit) that returns JSON health status.

DevOps alignment
----------------

- Reliable: Designed to reduce deployment failures and improve service uptime.
- Automatable: Designed to be executed in CI/CD pipelines (pre-deploy checks, post-deploy smoke tests).
- Observable: Emits structured outputs and metrics for dashboards and alerting.
- Lean: Small, focused checks to enable frequent, low-risk deployments.
- Measurable: Integrates with monitoring to improve MTTR and change failure rate.
- Shareable: Clear APIs, runbooks examples, and integration docs for teams.

Integration tips
-----------------

- Use canary deployments or blue-green deployments to minimize impact during rollouts.
- Use feature flags or conditional checks to avoid noisy alerts during rollouts.
- Run healthcheck.run_all in CI as a gating step for deployments.
- Expose metrics to Prometheus or your metrics backend for SLA tracking.

Configuration
-----------------

- Supports environment variables and optional YAML/JSON config for check registration.
- Default timeouts and thresholds are overridable per-check.

Contributing
-----------------

- Tests, type hints, and small, focused PRs welcome.
- Follow the repository's CONTRIBUTING.md and code-of-conduct.
- Add unit tests for new checks and integrations; CI runs linting and tests.
- Use GitHub issues for bugs, feature requests, and discussions.

License
-----------------

GNU GENERAL PUBLIC LICENSE v3

"""
# Version
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("streamlit_healthcheck")
except PackageNotFoundError:
    # package is not installed
    pass