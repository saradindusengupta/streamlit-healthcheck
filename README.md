
# Streamlit HealthCheck

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/streamlit-app-red)

> **Monitor, visualize, and manage the health of your Streamlit multi-page applications with ease.**

---

## Overview

Streamlit HealthCheck is a comprehensive health monitoring solution for Streamlit apps. It tracks system resources, external dependencies, and custom application checks, providing a real-time dashboard for operational insights and troubleshooting.

- **System Resource Monitoring:** CPU, memory, disk usage with configurable thresholds
- **Dependency Checks:** API endpoints and database connectivity status
- **Custom Health Checks:** Easily register and visualize custom checks for your app
- **Streamlit Page Error Tracking:** Detects exceptions and `st.error` calls across pages
- **Live Dashboard:** Interactive Streamlit UI with tabs for system, dependencies, custom checks, and page errors
- **Configurable:** All checks and thresholds are managed via a simple JSON config file

---

## Quickstart

```bash
# Install the library from pip
pip install streamlit_healthcheck

# Run the demo Streamlit application which includes a dashboard
streamlit run status_page/Home.py
```

---

## Features

| Feature              | Description                                                      |
|----------------------|------------------------------------------------------------------|
| System Health        | Monitors CPU, memory, disk usage with warning/critical thresholds |
| Dependency Checks    | Verifies API endpoints and database connections                   |
| Custom Checks        | Register custom health checks for your app logic                  |
| Page Error Tracking  | Captures exceptions and Streamlit errors per page                 |
| Live Dashboard       | Interactive UI with tabs and status indicators                    |
| Configurable         | JSON-based config for checks and thresholds                       |

---

## Configuration

All health check settings are managed via `config/health_check_config.json`. You can customize:

- Check intervals
- System resource thresholds
- API endpoints and database connections
- Custom checks

> [!TIP]
> Use the dashboard's configuration expander to adjust thresholds and save changes on the fly.

---

## Project Structure

```text
src/streamlit_healthcheck/      # Core healthcheck logic
status_page/                   # Streamlit UI pages
config/health_check_config.json # Health check configuration
requirements.txt               # Python dependencies
Makefile                       # Build and test commands
tests/                         # Unit tests
```

---

## Troubleshooting

> [!WARNING]
> If the dashboard reports a "critical" status, check the error details in the relevant tab. For API/database issues, verify connectivity and credentials. For system resource alerts, consider scaling your infrastructure.

---

## Getting Help

- [Library Documentation](https://docs.streamlit.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Issues & Discussions](https://github.com/saradindusengupta/streamlit-healthcheck/issues)

---
