# -*- coding: utf-8 -*-
"""
Streamlit Healthcheck

This package provides utilities for monitoring, reporting, and automating health checks in Streamlit applications.

## Features

- Automated health checks for Streamlit services
- Customizable health endpoints
- Integration with CI/CD pipelines for deployment validation
- Metrics collection and reporting for application status
- Extensible design for adding custom checks

## Usage

Import the package and use the provided functions to add health checks to your Streamlit app:

```python
from streamlit_healthcheck import healthcheck

# Example usage
status = healthcheck.run_all()
```

## DevOps Alignment

Designed to support continuous delivery and operational excellence by enabling automated, reliable health monitoring in Streamlit-based workflows.

## License

GNU GENERAL PUBLIC LICENSE V3

"""
# Version
__version__ = "1.0.0"