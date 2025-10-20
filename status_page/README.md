# How to run the demo Streamlit application

This directory also includes a demo Streamlit application which performs some basic cleaning , bi-variate and multivariate analysis and time-series regression. This is a multiple webapp with

- Home
  - Detailed Analysis
  - Regression
  - Health Check

This webapp has a single mismatch column name which will introduce an error intentionally to check if the `streamlit_healthcheck` is workign propeorly.

The `Health Check` page shows current healthcheck of the streamlit application. It is not necessary to include this page in real-world usecases, only decorating it  with appropriate decroator will work.

Before runnign the demo Streamlit app make sure to download the data from below mentioned source and keep it udner `/data` directory at the root of the app.

Download and install library from PyPI

```bash
pip install streamlit-healthcheck
```

Run the Streamlit application as

```bash
streamlit run Home.py --server.port=8501
```

Then run the FastAPI server using the integrated CLI as

```bash
python -m streamlit_healthcheck.streamlit-healthcheck-cli serve --host 127.0.0.1 --port 8080 --config streamlit-healthcheck/config/health_check_config.json --log-level DEBUG
```

This will spin-up a FastAPI server which can queried without auth to get all the necessary healthcheck info. The open api documentation woul dbe available at `/docs` endpoint

The config file can be used to set custom health checks for dependencies such as DBs and other API endpoints and also setup custom threshold for system reosurces for better alert and monitoring

[*Data source: Beijing PM2.5 Data*](https://archive.ics.uci.edu/dataset/381/beijing+pm2+5+data)
