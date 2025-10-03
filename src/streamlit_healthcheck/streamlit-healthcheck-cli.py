import click
import logging
import sys
from typing import Optional
from .server import start_api_server
"""
Streamlit Health Check CLI
This module provides a command-line interface (CLI) for monitoring the health of Streamlit applications.
It offers commands to start an API server for health checks and to initialize a new health check configuration file.
Commands:
---------
- serve:
    Starts the health check API server.
    Options:
        --host: Host address to bind the server (default: '0.0.0.0')
        --port: Port to run the server on (default: 8000)
        --config: Path to health check configuration file (default: 'config/health_check_config.json')
        --log-level: Set the logging level (choices: DEBUG, INFO, WARNING, ERROR, CRITICAL; default: INFO)
- init:
    Initializes a new health check configuration file.
    Options:
        --config: Path to health check configuration file (default: 'config/health_check_config.json')
Usage:
------
Run the CLI using the following command:
    python streamlit-healthcheck-cli.py [COMMAND] [OPTIONS]
Example:
--------
    python streamlit-healthcheck-cli.py serve --host 127.0.0.1 --port 8080 --config my_config.json --log-level DEBUG
    python streamlit-healthcheck-cli.py init --config my_config.json
Logging:
--------
Logging is configured to output to stdout with customizable log levels.
Error Handling:
---------------
All commands handle exceptions gracefully and provide informative error messages.
"""
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)



@click.group()
def cli():
    """Streamlit Health Check CLI - Monitor your Streamlit application health"""
    pass

@cli.command()
@click.option(
    '--host', 
    default='0.0.0.0',
    help='Host address to bind the server'
)
@click.option(
    '--port', 
    default=8000,
    type=int,
    help='Port to run the server on'
)
@click.option(
    '--config',
    default='config/health_check_config.json',
    type=click.Path(),
    help='Path to health check configuration file'
)
@click.option(
    '--log-level',
    default='INFO',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], case_sensitive=False),
    help='Set the logging level'
)
def serve(host: str, port: int, config: str, log_level: str):
    """Start the health check API server"""
    try:
        # Set logging level
        logging.getLogger().setLevel(log_level.upper())
        
        click.echo(f"Starting health check API server on {host}:{port}")
        click.echo(f"Using config file: {config}")
        click.echo(f"Log level: {log_level}")
        
        # Start the server
        start_api_server(host=host, port=port, config=config)
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
@click.option(
    '--config',
    default='config/health_check_config.json',
    type=click.Path(),
    help='Path to health check configuration file'
)
def init(config: str):
    """Initialize a new health check configuration file"""
    from .healthcheck import HealthCheckService
    
    try:
        service = HealthCheckService(config_path=config)
        service.save_config()
        click.echo(f"Created new configuration file at: {config}")
        
    except Exception as e:
        logger.error(f"Failed to create config file: {str(e)}")
        raise click.ClickException(str(e))

def main():
    """
    Entry point for the Streamlit Healthcheck CLI.
    Attempts to execute the CLI command and handles any unexpected exceptions
    by logging the error and exiting the program with a non-zero status code.
    """
    
    try:
        cli()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()