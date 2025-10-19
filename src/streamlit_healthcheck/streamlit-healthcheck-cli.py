# -*- coding: utf-8 -*-
"""
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

```bash
python -m streamlit-healthcheck.streamlit-healthcheck-cli [COMMAND] [OPTIONS]
```

Example:
--------

Start the server with default configuration

```bash
python -m streamlit-healthcheck.streamlit-healthcheck-cli serve
```

Start the server with custom configuration

```bash
python -m streamlit-healthcheck.streamlit-healthcheck-cli serve --host 127.0.0.1 --port 8080 --config my_config.json --log-level DEBUG
```


Initialize a new configuration file

```bash
python -m streamlit-healthcheck.streamlit-healthcheck-cli init --config my_config.json
```


Logging:
--------

Logging is configured to output to stdout with customizable log levels.

Error Handling:
---------------

All commands handle exceptions gracefully and provide informative error messages.
"""
import click
import logging
import sys
from typing import Optional
from .server import start_api_server
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
    """
    Command-line entry point for the streamlit-healthcheck tool.
    This function implements the command-line interface (CLI) used to run
    health checks against a Streamlit application or to serve a small
    healthcheck UI. It is intended to be registered as a console_script
    entry point for the package.
    
    Behavior
    --------
    
    - Parse command-line arguments (e.g. target URL of the Streamlit app,
        timeout values, logging/verbosity flags, and optional configuration
        file path).
    - Validate arguments and configuration.
    - Execute one or more health checks (HTTP / status checks, simple page
        content assertions, or custom checks defined in a config).
    - Optionally start a lightweight HTTP server that exposes the healthcheck
        results or a human-readable status page.
    - Emit structured logs and progress information to stdout/stderr.
    - Exit with a zero status on success and non-zero on failure or error.
    
    Arguments
    ---------
    
    - None (reads configuration from sys.argv and environment).
    Return
    - None. On completion the function typically calls sys.exit() with an
        appropriate exit code.
        
    Exit codes
    -----------
    
    - 0: All health checks passed.
    - 1: One or more health checks failed.
    - 2: Invalid usage or configuration.
    - 3: Unexpected runtime error (network failure, internal exception).
    
    Side effects
    ------------
    
    - Network requests to the target Streamlit instance.
    - May bind to a local port if serving a status UI.
    - Configures global logging and may call sys.exit().
    
    Examples
    --------
    
    - Run checks against a local Streamlit app:
            streamlit-healthcheck --url http://localhost:8501 --timeout 5
    - Serve a status UI on port 9000:
            streamlit-healthcheck --serve --port 9000 --config /path/to/config.yml
    Notes
    -----
    
    - The exact CLI flags and behavior are defined by the implemented argument
        parser; this docstring describes the intended responsibilities and
        observable outcomes of the CLI entry point.
    """
    
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
    """
    Start the health check API server.
    Sets the global logging level, prints startup information to the console, and
    invokes the underlying server start function. Any exception raised during
    startup is logged and re-raised as a click.ClickException.
    
    Parameters
    ----------
    
    host : str
        Hostname or IP address to bind the server to (e.g. "0.0.0.0" or "127.0.0.1").
    port : int
        TCP port number to listen on.
    config : str
        Filesystem path to the configuration file used to configure the health check API.
    log_level : str
        Logging level name (case-insensitive), e.g. "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL".
    
    Raises
    ------
    
    click.ClickException
        If an unexpected error occurs while starting the server; the underlying
        exception message is propagated.
        
    Side effects
    ------------
    
    - Calls logging.getLogger().setLevel to adjust the global logging level.
    - Emits informational messages via click.echo.
    - Calls start_api_server(host, port, config) to start the service.
    - On failure, logs the error via logger.error before raising a click.ClickException.
    """
    
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
    """
    Initialize and persist a healthcheck service configuration.
    Creates a HealthCheckService for the given configuration path, writes the default
    configuration to disk, and prints a success message to stdout. Any failure during
    service creation or saving is logged and re-raised as a click.ClickException so
    CLI callers receive a clean, user-facing error.
    
    Args:
        config (str): Path to the configuration file to create.
        
    Raises:
        click.ClickException: If the configuration file could not be created or saved.
    """
    
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
    Run the command-line interface and handle top-level exceptions.
    This function acts as the script entry point. It calls the module-level cli()
    function to execute the command-line interface. Any exception raised during
    cli() execution is caught, logged via the module-level logger, and causes the
    process to exit with status code 1.
    
    Behavior:
    
    - Calls cli().
    - On successful completion, returns normally (None).
    - On any Exception, logs an error message with logger.error and terminates
        the process by calling sys.exit(1).
        
    Dependencies:
    
    - Expects cli, logger, and sys to be available in the module namespace.
    
    Usage:
    
    Intended to be invoked when the package/script is run as a program (e.g. from
    if __name__ == "__main__": main()).
    """
    try:
        cli()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()