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
    default='/home/saradindu/dev/streamlit-healthcheck/config/health_check_config.json',
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
    default='/home/saradindu/dev/streamlit-healthcheck/config/health_check_config.json',
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
    """Main entry point for the CLI"""
    try:
        cli()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()