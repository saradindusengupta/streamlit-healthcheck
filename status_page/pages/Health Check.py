# Example usage in a multi-page Streamlit app
# Add this to the pages/health_check.py file in your Streamlit app

"""
Example usage in a multi-page Streamlit app
"""
import streamlit as st
from datetime import datetime
import sys
from streamlit_healthcheck.healthcheck import health_check

# Set the page title and icon

st.set_page_config(
    page_title="Health Dashboard",
    page_icon="🩺",
    layout="wide"
)

config_file = "config/health_check_config.json"
health_check(config_path=config_file)


# Example of how to use a custom health check
"""
Example of registering a custom health check

Define a custom health check function
"""
def check_database_connection():
    try:
        # Replace with actual database connection check
        is_connected = True  # Simulate connection check
        return {
            "status": "healthy" if is_connected else "critical",
            "connection_time_ms": 15.2,  # Example metric
            "message": "Successfully connected to database"
        }
    except Exception as e:
        return {
            "status": "critical",
            "error": str(e)
        }

# Register the custom check with the health check service
st.session_state.health_service.register_custom_check(
    "database_connection", 
    check_database_connection
)