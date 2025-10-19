import streamlit as st
import psutil
import pandas as pd
import requests
import time
import threading
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
import functools
import traceback
import logging
import sqlite3

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StreamlitPageMonitor:
    """
    Singleton class that monitors and records errors occurring within Streamlit pages.
    It captures both explicit Streamlit error messages (monkey-patching st.error) and
    uncaught exceptions raised during the execution of monitored page functions, and
    persists error details to a local SQLite database.
    
    Key responsibilities
    
    - Intercept Streamlit error calls by monkey-patching st.error and record them with
        a stack trace, timestamp, status, and type.
    - Provide a decorator `monitor_page(page_name)` to set a page context, capture
        exceptions raised while rendering/executing a page, and record those exceptions.
    - Store errors in an in-memory structure grouped by page and persist them to
        an SQLite database for later inspection.
    - Provide utilities to load, deduplicate, clear, and query stored errors.
    
    Behavior and side effects
    
    - Implements the Singleton pattern: only one instance exists per Python process.
    - On first instantiation, optionally accepts a custom db_path and initializes
        the SQLite database and its parent directory (creating it if necessary).
    - Monkey-patches `streamlit.error` (st.error) to capture calls and still forward
        them to the original st.error implementation.
    - Records the following fields for each error: page, error, traceback, timestamp,
        status, type. The SQLite table `errors` mirrors these fields and includes an
        auto-incrementing `id`.
    - Persists errors immediately to SQLite when captured; database IO errors are
        logged but do not suppress the original exception (for monitored exceptions,
        the exception is re-raised after recording).
        
    Public API (methods)
    
    - __new__(cls, db_path=None)
            Create or return the singleton StreamlitPageMonitor instance.
        
            Parameters
            ----------
            db_path : Optional[str]
                If provided on the first instantiation, overrides the class-level
                database path used to persist captured Streamlit error information.
                
            Returns
            -------
            StreamlitPageMonitor
                The singleton instance of the class.
                
            Behavior
            --------
            - On first instantiation (when cls._instance is None):
            - Allocates the singleton via super().__new__.
            - Optionally sets cls._db_path from the provided db_path.
            - Logs the configured DB path.
            - Monkey-patches streamlit.error (st.error) with a wrapper that:
                - Builds an error record containing the error text, a formatted stack trace,
                ISO timestamp, severity/status, an error type marker, and the current page.
                - Normalizes a missing current page to "unknown_page".
                - Stores the record in the in-memory cls._errors dictionary keyed by page.
                - Attempts to persist the record to the SQLite DB using cls().save_errors_to_db,
                logging any persistence errors without interrupting Streamlit's normal error display.
                - Calls the original st.error to preserve expected UI behavior.
            - Initializes the SQLite DB via cls._init_db().
            - On subsequent calls:
            - Returns the existing singleton instance.
            - If db_path is provided, updates cls._db_path for future use.
            
            Side effects
            ------------
            - Replaces st.error globally for the running process.
            - Writes error records to both an in-memory structure (cls._errors) and to the
            configured SQLite database (if persistence succeeds).
            - Logs informational and error messages.
            
            Notes
            -----
            - The method assumes the class defines/has: _instance, _db_path, _current_page,
            _errors, _st_error (original st.error), save_errors_to_db, and _init_db.
            - Exceptions raised during saving of individual errors are caught and logged;
            exceptions from instance creation or DB initialization may propagate.
            - The implementation is not explicitly thread-safe; concurrent instantiation
            attempts may require external synchronization if used in multi-threaded contexts.
    - set_page_context(cls, page_name: str)
            Set the current page name used when recording subsequent errors.
    - monitor_page(cls, page_name: str) -> Callable
            Decorator for page rendering/execution functions. Sets the page context,
            clears previously recorded non-Streamlit errors for that page, runs the
            function, records and persists any raised exception, and re-raises it.
    - _handle_st_error(cls, error_message: str)
    
            Handles Streamlit-specific errors by recording error details for the current page.
        
            Args:
                error_message (str): The error message to be logged.
                
            Side Effects:
                Updates the class-level _errors dictionary with error information for the current Streamlit page.
                
            Error Information Stored:
                - error: Formatted error message.
                - traceback: Stack trace at the point of error.
                - timestamp: Time when the error occurred (ISO format).
                - status: Error severity ('critical').
                - type: Error type ('streamlit_error').
    - get_page_errors(cls) -> dict
            Load errors from the database and return a dictionary mapping page names to
            lists of error dicts. Performs basic deduplication by error message.
    - save_errors_to_db(cls, errors: Iterable[dict])
            Persist a list of error dictionaries to the configured SQLite database.
            Ensures traceback is stored as a string (JSON if originally a list).
    - clear_errors(cls, page_name: Optional[str] = None)
            Clear in-memory errors for a specific page or all pages and delete matching
            rows from the database.
    - _init_db(cls)
            Ensure the database directory exists and create the `errors` table if it
            does not exist.
    - load_errors_from_db(cls, page=None, status=None, limit=None) -> List[dict]
            Query the database for errors, optionally filtering by page and/or status,
            returning a list of error dictionaries ordered by timestamp (descending)
            and limited if requested.
            
    Storage and format
    
    - Default DB path: ~/local/share/streamlit-healthcheck/streamlit_page_errors.db (overridable).
    - SQLite table `errors` columns: id, page, error, traceback, timestamp, status, type.
    - Tracebacks may be stored as JSON strings (if originally lists) or plain strings.
    Concurrency and robustness
    - Designed for single-process usage typical of Streamlit apps. The singleton and
        monkey-patching are process-global.
    - Database interactions use short-lived connections; callers should handle any
        exceptions arising from DB access (errors are logged internally).
    - Decorator preserves original function metadata via functools.wraps.
    
    Examples
    
    - Use as a decorator on page render function:
    >>> @StreamlitPageMonitor.monitor_page("home")
    >>> def render_home():

    - Set page context manually:
    >>> StreamlitPageMonitor.set_page_context("settings")
    
    - Set custom DB path on first instantiation:
    >>> # Place this at the top of your Streamlit app once, before any error monitoring or decorator usage to ensure the sqlite
    >>> # database is created properly at the specified path; otherwise it will default to a temp directory. The temp directory
    >>> # will be `~/local/share/streamlit-healthcheck/streamlit_page_errors.db`.
    >>> StreamlitPageMonitor(db_path="/home/saradindu/dev/streamlit_page_errors.db")
    ...

    SQLite Database Schema
    ---------------------
    The following schema is used for persisting errors:

    ```sql
    CREATE TABLE IF NOT EXISTS errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page TEXT,
        error TEXT,
        traceback TEXT,
        timestamp TEXT,
        status TEXT,
        type TEXT
    );
    ```

    Field Descriptions:

    | Column     | Type    | Description                                 |
    |------------|---------|---------------------------------------------|
    | id         | INTEGER | Auto-incrementing primary key               |
    | page       | TEXT    | Name of the Streamlit page                  |
    | error      | TEXT    | Error message                               |
    | traceback  | TEXT    | Stack trace or traceback (as string/JSON)   |
    | timestamp  | TEXT    | ISO8601 timestamp of error occurrence       |
    | status     | TEXT    | Severity/status (e.g., 'critical')          |
    | type       | TEXT    | Error type ('streamlit_error', 'exception') |

    Example:
    
    >>> @StreamlitPageMonitor.monitor_page("home")
    >>> def render_home():
    
    Notes
    
    - The class monkey-patches st.error globally when first instantiated; ensure
        this side effect is acceptable in your environment.
    - Errors captured by st.error that occur outside any known page are recorded
        under the page name "unknown_page".
    - The schema is created/ensured in `_init_db()`.
    - Tracebacks may be stored as JSON strings or plain text.
    - Errors are persisted immediately upon capture.
    
    """
    _instance = None
    _errors: Dict[str, List[Dict[str, Any]]] = {}
    _st_error = st.error
    _current_page = None

    # --- SQLite schema for error persistence ---
    # Table: errors
    # Fields:
    #   id INTEGER PRIMARY KEY AUTOINCREMENT
    #   page TEXT
    #   error TEXT
    #   traceback TEXT
    #   timestamp TEXT
    #   status TEXT
    #   type TEXT
    
    # Local development DB path
    #_db_path = os.path.join(os.path.expanduser("~"), "dev", "streamlit-healthcheck", "streamlit_page_errors.db")
    # Final build DB path
    _db_path = os.path.join(os.path.expanduser("~"), ".local", "share", "streamlit-healthcheck", "streamlit_page_errors.db")

    def __new__(cls, db_path=None):
        """
        Create or return the singleton StreamlitPageMonitor instance.
        """
        
        if cls._instance is None:
            cls._instance = super(StreamlitPageMonitor, cls).__new__(cls)
            # Allow db_path override at first instantiation
            if db_path is not None:
                cls._db_path = db_path
            logger.info(f"StreamlitPageMonitor DB path set to: {cls._db_path}")
            # Monkey patch st.error to capture error messages
            def patched_error(*args, **kwargs):
                error_message = " ".join(str(arg) for arg in args)
                current_page = cls._current_page
                error_info = {
                    'error': error_message,
                    'traceback': traceback.format_stack(),
                    'timestamp': datetime.now().isoformat(),
                    'status': 'critical',
                    'type': 'streamlit_error',
                    'page': current_page
                }
                # Ensure current_page is a string, not None
                if current_page is None:
                    current_page = "unknown_page"
                if current_page not in cls._errors:
                    cls._errors[current_page] = []
                cls._errors[current_page].append(error_info)
                # Persist to DB
                try:
                    cls().save_errors_to_db([error_info])
                except Exception as e:
                    logger.error(f"Failed to save Streamlit error to DB: {e}")
                # Call original st.error
                return cls._st_error(*args, **kwargs)

            st.error = patched_error

            # Initialize SQLite database
            cls._init_db()
        else:
            # If already instantiated, allow updating db_path if provided
            if db_path is not None:
                cls._db_path = db_path
        return cls._instance

    @classmethod
    def _handle_st_error(cls, error_message: str):
        """
        Handles Streamlit-specific errors by recording error details for the current page.
        """
        
        # Get current page name from Streamlit context
        current_page = getattr(st, '_current_page', 'unknown_page')
        error_info = {
            'error': f"Streamlit Error: {error_message}",
            'traceback': traceback.format_stack(),
            'timestamp': datetime.now().isoformat(),
            'status': 'critical',
            'type': 'streamlit_error',
            'page': current_page
        }
        # Initialize list for page if not exists
        if current_page not in cls._errors:
            cls._errors[current_page] = []
        # Add new error
        cls._errors[current_page].append(error_info)
        # Persist to DB
        try:
            cls().save_errors_to_db([error_info])
        except Exception as e:
            logger.error(f"Failed to save Streamlit error to DB: {e}")

    @classmethod
    def set_page_context(cls, page_name: str):
        """Set the current page context"""
        cls._current_page = page_name

    @classmethod
    def monitor_page(cls, page_name: str):
        """
        Decorator to monitor and log exceptions for a specific Streamlit page.
        
        Args:
            page_name (str): The name of the page to monitor.
            
        Returns:
            Callable: A decorator that wraps the target function, sets the page context,
            clears previous non-Streamlit errors, and logs any exceptions that occur during execution.
            
        The decorator performs the following actions:
        
            - Sets the current page context using `cls.set_page_context`.
            - Clears previous exception errors for the page, retaining only those marked as 'streamlit_error'.
            - Executes the wrapped function.
            - If an exception occurs, logs detailed error information (error message, traceback, timestamp, status, type, and page)
              to `cls._errors` under the given page name, then re-raises the exception.
        """
        
        def decorator(func):
            """
            Decorator to manage page-specific error handling and context setting.
            This decorator sets the current page context before executing the decorated function.
            It clears previous exception errors for the page, retaining only Streamlit error calls.
            If an exception occurs during function execution, it captures error details including
            the error message, traceback, timestamp, status, type, and page name, and appends them
            to the page's error log. The exception is then re-raised.
            
            Args:
                func (Callable): The function to be decorated.
                
            Returns:
                Callable: The wrapped function with error handling and context management.
            """
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Set the current page context
                cls.set_page_context(page_name)
                try:
                    # Clear previous exception errors but keep st.error calls
                    if page_name in cls._errors:
                        cls._errors[page_name] = [
                            e for e in cls._errors[page_name]
                            if e.get('type') == 'streamlit_error'
                        ]
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error_info = {
                        'error': str(e),
                        'traceback': traceback.format_exc(),
                        'timestamp': datetime.now().isoformat(),
                        'status': 'critical',
                        'type': 'exception',
                        'page': page_name
                    }
                    if page_name not in cls._errors:
                        cls._errors[page_name] = []
                    cls._errors[page_name].append(error_info)
                    # Persist to DB
                    try:
                        cls().save_errors_to_db([error_info])
                    except Exception as db_exc:
                        logger.error(f"Failed to save exception error to DB: {db_exc}")
                    raise
            return wrapper
        return decorator

    @classmethod
    def get_page_errors(cls):
        """
        Load error records from storage and return them grouped by page.
        This class method calls cls().load_errors_from_db() to retrieve a sequence of error records
        (each expected to be a mapping). It normalizes each record to a dictionary with the keys:
        
            - 'error' (str): error message, default "Unknown error"
            - 'traceback' (list): traceback frames or lines, default []
            - 'timestamp' (str): timestamp string, default ""
            - 'type' (str): error type/category, default "unknown"
            
        Grouping and uniqueness:
        
            - Records are grouped by the 'page' key; if a record has no 'page' key, the page name
                "unknown" is used.
            - For each page, only unique errors are kept using the 'error' string as the deduplication
                key. When multiple records for the same page have the same 'error' value, the last
                occurrence in the loaded sequence will be retained.
                
        Return value:
        
            - dict[str, list[dict]]: mapping from page name to a list of normalized error dicts.
            
        Error handling:
        
            - Any exception raised while loading or processing records will be logged via logger.error.
                The method will return the result accumulated so far (or an empty dict if nothing was
                accumulated).
                
        Notes:
        
            - The class is expected to be instantiable (cls()) and to provide a load_errors_from_db()
                method that yields or returns an iterable of mappings.
        """
        
        result = {}
        try:
            db_errors = cls().load_errors_from_db()
            for err in db_errors:
                page = err.get('page', 'unknown')
                if page not in result:
                    result[page] = []
                result[page].append({
                    'error': err.get('error', 'Unknown error'),
                    'traceback': err.get('traceback', []),
                    'timestamp': err.get('timestamp', ''),
                    'type': err.get('type', 'unknown')
                })
            # Return only unique page errors using the 'page' column for filtering
            return {page: list({e['error']: e for e in errors}.values()) for page, errors in result.items()}
        except Exception as e:
            logger.error(f"Failed to load errors from DB: {e}")
            return result

    @classmethod
    def save_errors_to_db(cls, errors):
        """
        Save a sequence of error records into the SQLite database configured at cls._db_path.
        
        Parameters
        ----------
        
        errors : Iterable[Mapping] | list[dict]
        
            Sequence of error records to persist. Each record is expected to be a mapping with the
            following keys (values are stored as provided, except for traceback which is normalized):
            
              - "page": identifier or name of the page where the error occurred (str)
              - "error": human-readable error message (str)
              - "traceback": traceback information; may be a str, list, or None. If a list, it will be
                JSON-encoded before storage. If None, an empty string is stored.
              - "timestamp": timestamp for the error (stored as provided)
              - "status": status associated with the error (str)
              - "type": classification/type of the error (str)
              
        Behavior
        --------
        
        - If `errors` is falsy (None or empty), the method returns immediately without touching the DB.
        - Opens a SQLite connection to the path stored in `cls._db_path`.
        - Iterates over the provided records and inserts each into the `errors` table with columns
          (page, error, traceback, timestamp, status, type).
        - Ensures that the `traceback` value is always written as a string (list -> JSON string,
          other values -> str(), None -> "").
        - Commits the transaction if all inserts succeed and always closes the connection in a finally block.
        
        Exceptions
        ----------
        
        - Underlying sqlite3 exceptions (e.g., sqlite3.Error) are not swallowed and will propagate to the caller
          if connection/execution fails.
          
        Returns
        -------
        
        None
        """
        if not errors:
            return
        conn = sqlite3.connect(cls._db_path)
        try:
            cursor = conn.cursor()
            for err in errors:
                # Ensure traceback is always a string for SQLite
                tb = err.get("traceback")
                if isinstance(tb, list):
                    import json
                    tb_str = json.dumps(tb)
                else:
                    tb_str = str(tb) if tb is not None else ""
                cursor.execute(
                    """
                    INSERT INTO errors (page, error, traceback, timestamp, status, type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        err.get("page"),
                        err.get("error"),
                        tb_str,
                        err.get("timestamp"),
                        err.get("status"),
                        err.get("type"),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def clear_errors(cls, page_name: Optional[str] = None):
        """Clear stored health-check errors for a specific page or for all pages.
        This classmethod updates both the in-memory error cache and the persistent
        SQLite-backed store.
        
        If `page_name` is provided:
        
        - Remove the entry for that page from the class-level in-memory dictionary
            of errors (if present).
        - Delete all rows in the SQLite `errors` table where `page` equals `page_name`.
        
        If `page_name` is None:
        
        - Clear the entire in-memory errors dictionary.
        - Delete all rows from the SQLite `errors` table.
        
        Args:
                page_name (Optional[str]): Name of the page whose errors should be cleared.
                        If None, all errors are cleared.
                        
        Returns:
                None
                
        Side effects:
        
                - Mutates class-level state (clears entries in `cls._errors`).
                - Opens a SQLite connection to `cls._db_path` and executes DELETE statements
                    against the `errors` table. Commits the transaction and closes the connection.
                    
        Error handling:
        
                - Database-related exceptions are caught and logged via the module logger;
                    they are not re-raised by this method. As a result, callers should not
                    rely on exceptions to detect DB failures.
                    
        Notes:
        
                - The method assumes `cls._db_path` points to a valid SQLite database file
                    and that an `errors` table exists with a `page` column.
                - This method does not provide synchronization; callers should take care of
                    concurrent access to class state and the database if used from multiple
                    threads or processes.
        """
        
        if page_name:
            if page_name in cls._errors:
                del cls._errors[page_name]
            # Remove from DB
            try:
                conn = sqlite3.connect(cls._db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM errors WHERE page = ?", (page_name,))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to clear errors from DB for page {page_name}: {e}")
        else:
            cls._errors = {}
            # Remove all from DB
            try:
                conn = sqlite3.connect(cls._db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM errors")
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to clear all errors from DB: {e}")

    @classmethod
    def _init_db(cls):
        """
        Initialize the SQLite database file and ensure the required schema exists.
        This class-level initializer performs the following steps:
        
        - Ensures the parent directory of cls._db_path exists; creates it if necessary.
            - If cls._db_path has no parent directory (e.g., a bare filename), no directory is created.
        - Connects to the SQLite database at cls._db_path (creating the file if it does not exist).
        - Creates an "errors" table if it does not already exist with the following columns:
            - id (INTEGER PRIMARY KEY AUTOINCREMENT)
            - page (TEXT)
            - error (TEXT)
            - traceback (TEXT)
            - timestamp (TEXT)
            - status (TEXT)
            - type (TEXT)
        - Commits the schema change and closes the database connection.
        - Logs informational and error messages using the module logger.
        
        Parameters
        ----------
        
        cls : type
        
                The class on which this method is invoked. Must provide a valid string attribute
                `_db_path` indicating the target SQLite database file path.
                
        Raises
        ------
        
        Exception
        
                Re-raises exceptions encountered when creating the parent directory (os.makedirs).
                
        sqlite3.Error
        
                May be raised by sqlite3.connect or subsequent SQLite operations when the database
                cannot be opened or initialized.
                
        Side effects
        ------------
        
        - May create directories on the filesystem.
        - May create or modify the SQLite database file at cls._db_path.
        - Writes log messages via the module logger.
        
        Returns
        -------
        
        None
        """
        
        # Ensure the parent directory for the DB exists
        db_dir = os.path.dirname(cls._db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=False)
                logger.info(f"Created directory for DB: {db_dir}")
            except Exception as e:
                logger.error(f"Failed to create DB directory {db_dir}: {e}")
                raise
        # Now create/connect to the DB and table
        logger.info(f"Initializing SQLite DB at: {cls._db_path}")
        conn = sqlite3.connect(cls._db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page TEXT,
            error TEXT,
            traceback TEXT,
            timestamp TEXT,
            status TEXT,
            type TEXT
        )''')
        conn.commit()
        conn.close()
    @classmethod
    def load_errors_from_db(cls, page=None, status=None, limit=None):
        """
        Load errors from the class SQLite database.
        This classmethod connects to the SQLite database at cls._db_path, queries the
        'errors' table, and returns matching error records as a list of dictionaries.
        
        Parameters:
        
            page (Optional[str]): If provided, filter results to rows where the 'page'
                column equals this value.
            status (Optional[str]): If provided, filter results to rows where the 'status'
                column equals this value.
            limit (Optional[int|str]): If provided, limits the number of returned rows.
                The value is cast to int internally; a non-convertible value will raise
                ValueError.
                
        Returns:
        
            List[dict]: A list of dictionaries representing rows from the 'errors' table.
            Each dict contains the following keys:
                - id: primary key (int)
                - page: page identifier (str)
                - error: short error message (str)
                - traceback: full traceback or diagnostic text (str)
                - timestamp: stored timestamp value as retrieved from the DB (type depends on schema)
                - status: error status (str)
                - type: error type/category (str)
                
        Raises:
        
            ValueError: If `limit` cannot be converted to int.
            sqlite3.Error: If an SQLite error occurs while executing the query.
            
        Notes:
        
            - Uses parameterized queries for the 'page' and 'status' filters to avoid SQL
              injection. The `limit` is applied after casting to int.
            - Results are ordered by `timestamp` in descending order.
            - The database connection is always closed in a finally block to ensure cleanup.
        """
        
        conn = sqlite3.connect(cls._db_path)
        try:
            cursor = conn.cursor()
            query = "SELECT id, page, error, traceback, timestamp, status, type FROM errors"
            params = []
            filters = []
            if page:
                filters.append("page = ?")
                params.append(page)
            if status:
                filters.append("status = ?")
                params.append(status)
            if filters:
                query += " WHERE " + " AND ".join(filters)
            query += " ORDER BY timestamp DESC"
            if limit:
                query += f" LIMIT {int(limit)}"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            errors = []
            for row in rows:
                errors.append({
                    "id": row[0],
                    "page": row[1],
                    "error": row[2],
                    "traceback": row[3],
                    "timestamp": row[4],
                    "status": row[5],
                    "type": row[6],
                })
            return errors
        finally:
            conn.close()

class HealthCheckService:
    """
    A background-capable health monitoring service for a Streamlit-based application.
    This class periodically executes a configurable set of checks (system metrics,
    external dependencies, Streamlit server and pages, and user-registered custom checks),
    aggregates their results, and exposes a sanitized health snapshot suitable for UI
    display or remote monitoring.
    
    Primary responsibilities
    
    - Load and persist a JSON configuration that defines check intervals, thresholds,
        dependencies to probe, and Streamlit connection settings.
    - Run periodic checks in a dedicated background thread (start/stop semantics).
    - Collect system metrics (CPU, memory, disk) using psutil and apply configurable
        warning/critical thresholds.
    - Probe configured HTTP API endpoints and (placeholder) database checks.
    - Verify Streamlit server liveness by calling a /healthz endpoint and inspect
        Streamlit page errors via StreamlitPageMonitor.
    - Allow callers to register synchronous custom checks (functions returning dicts).
    - Compute an aggregated overall status (critical > warning > unknown > healthy).
    - Provide a sanitized snapshot of health data with function references removed for safe
        serialization/display.
        
    Usage (high level)
    
    - Instantiate: svc = HealthCheckService(config_path="path/to/config.json")
    - Optionally register custom checks: svc.register_custom_check("my_check", my_check_func)
        where my_check_func() -> Dict[str, Any]
    - Start background monitoring: svc.start()
    - Stop monitoring: svc.stop()
    - Retrieve current health snapshot for display or API responses: svc.get_health_data()
    - Persist any changes to configuration: svc.save_config()
    
    Configuration (JSON)
    
    - check_interval: int (seconds) — how often to run the checks (default 60)
    - streamlit_url: str — base host (default "http://localhost")
    - streamlit_port: int — port for Streamlit server (default 8501)
    - system_checks: { "cpu": bool, "memory": bool, "disk": bool }
    - dependencies:
            - api_endpoints: list of { "name": str, "url": str, "timeout": int }
            - databases: list of { "name": str, "type": str, "connection_string": str }
    - thresholds:
            - cpu_warning, cpu_critical, memory_warning, memory_critical, disk_warning, disk_critical
            
    Health data structure (conceptual)
    
    - last_updated: ISO timestamp
    - system: { "cpu": {...}, "memory": {...}, "disk": {...} }
    - dependencies: { "<name>": {...}, ... }
    - custom_checks: { "<name>": {...} }  (get_health_data() strips callable references)
    - streamlit_server: {status, response_code/latency/error, message, url}
    - streamlit_pages: {status, error_count, errors, details}
    - overall_status: "healthy" | "warning" | "critical" | "unknown"
    
    Threading and safety
    
    - The service runs checks in a daemon thread started by start(). stop() signals the
        thread to terminate and joins with a short timeout. Clients should avoid modifying
        internal structures concurrently; get_health_data() returns a sanitized snapshot
        appropriate for concurrent reads.
        
    Custom checks
    
    - register_custom_check(name, func): registers a synchronous function that returns a
        dict describing the check result (must include a "status" key with one of the
        recognized values). The service stores the function reference internally but returns
        sanitized results via get_health_data().
        
    Error handling and logging
    
    - Individual checks catch exceptions and surface errors in the corresponding
        health_data entry with status "critical" where appropriate.
    - The Streamlit UI integration (st.* calls) is used for user-visible error messages
        when loading/saving configuration; the service also logs events to its configured
        logger.
        
    Extensibility notes
    
    - Database checks are left as placeholders; implement _check_database for specific DB
        drivers/connections.
    - Custom checks are synchronous; if long-running checks are required, adapt the
        registration/run pattern to use async or worker pools.
    """
    def __init__(self, config_path: str = "health_check_config.json"):
        """
        Initializes the HealthCheckService instance.
        
        Args:
            config_path (str): Path to the health check configuration file. Defaults to "health_check_config.json".
            
        Attributes:
        
        - logger (logging.Logger): Logger for the HealthCheckService.
        - config_path (str): Path to the configuration file.
        - health_data (Dict[str, Any]): Dictionary storing health check data.
        - config (dict): Loaded configuration from the config file.
        - check_interval (int): Interval in seconds between health checks. Defaults to 60.
        - _running (bool): Indicates if the health check service is running.
        - _thread (threading.Thread or None): Thread running the health check loop.
        - streamlit_url (str): URL of the Streamlit service. Defaults to "http://localhost".
        - streamlit_port (int): Port of the Streamlit service. Defaults to 8501.
        """
        self.logger = logging.getLogger(f"{__name__}.HealthCheckService")
        self.logger.info("Initializing HealthCheckService")
        self.config_path = config_path
        self.health_data: Dict[str, Any] = {
            "last_updated": None,
            "system": {},
            "dependencies": {},
            "custom_checks": {},
            "overall_status": "unknown"
        }
        self.config = self._load_config()
        self.check_interval = self.config.get("check_interval", 60)  # Default: 60 seconds
        self._running = False
        self._thread = None
        self.streamlit_url = self.config.get("streamlit_url", "http://localhost")
        self.streamlit_port = self.config.get("streamlit_port", 8501)  # Default: 8501
    def _load_config(self) -> Dict:
        """Load health check configuration from file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading health check config: {str(e)}")
                return self._get_default_config()
        else:
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict:
        """Return default health check configuration."""
        return {
            "check_interval": 60,
            "streamlit_url": "http://localhost",
            "streamlit_port": 8501,
            "system_checks": {
                "cpu": True,
                "memory": True,
                "disk": True
            },
            "dependencies": {
                "api_endpoints": [
                    # Example API endpoint to check
                    {"name": "example_api", "url": "https://httpbin.org/get", "timeout": 5}
                ],
                "databases": [
                    # Example database connection to check
                    {"name": "main_db", "type": "postgres", "connection_string": "..."}
                ]
            },
            "thresholds": {
                "cpu_warning": 70,
                "cpu_critical": 90,
                "memory_warning": 70,
                "memory_critical": 90,
                "disk_warning": 70,
                "disk_critical": 90
            }
        }
    
    def start(self):
        """
        Start the periodic health-check background thread.
        If the `healthcheck` runner is already active, this method is a no-op and returns
        immediately. Otherwise, it marks the runner as running, creates a daemon thread
        targeting self._run_checks_periodically, stores the thread on self._thread, and
        starts it.
        
        Behavior and side effects:
        
        - Idempotent while running: repeated calls will not create additional threads.
        - Sets self._running to True.
        - Assigns a daemon threading.Thread to self._thread and starts it.
        - Non-blocking: returns after starting the background thread.
        - The daemon thread will not prevent the process from exiting.
        
        Thread-safety:
        
        - If start() may be called concurrently from multiple threads, callers should
            ensure proper synchronization (e.g., external locking) to avoid race conditions.
            
        Returns:
        
                None
        """
        
        if self._running:
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._run_checks_periodically, daemon=True)
        self._thread.start()
        
    def stop(self):
        """Stop the health check service."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            
    def _run_checks_periodically(self):
        """Run health checks periodically based on check interval."""
        while self._running:
            self.run_all_checks()
            time.sleep(self.check_interval)
            
    def run_all_checks(self):
        """Run all configured health checks and update health data."""
        # Update timestamp
        self.health_data["last_updated"] = datetime.now().isoformat()
        
        # Check Streamlit server
        self.health_data["streamlit_server"] = self.check_streamlit_server()
        
        # System checks
        if self.config["system_checks"].get("cpu", True):
            self.check_cpu()
        if self.config["system_checks"].get("memory", True):
            self.check_memory()
        if self.config["system_checks"].get("disk", True):
            self.check_disk()
            
        # Rest of the existing checks...
        self.check_dependencies()
        self.run_custom_checks()
        self.check_streamlit_pages()
        self._update_overall_status()
        
    def check_cpu(self):
        """
        Checks the current CPU usage and updates the health status based on configured thresholds.
        Measures the CPU usage percentage over a 1-second interval using psutil. Compares the result
        against warning and critical thresholds defined in the configuration. Sets the status to
        'healthy', 'warning', or 'critical' accordingly, and updates the health data dictionary.
        
        Returns:
        
            None
        """
        
        cpu_percent = psutil.cpu_percent(interval=1)
        warning_threshold = self.config["thresholds"].get("cpu_warning", 70)
        critical_threshold = self.config["thresholds"].get("cpu_critical", 90)
        
        status = "healthy"
        if cpu_percent >= critical_threshold:
            status = "critical"
        elif cpu_percent >= warning_threshold:
            status = "warning"
            
        self.health_data["system"]["cpu"] = {
            "usage_percent": cpu_percent,
            "status": status
        }
        
    def check_memory(self):
        """
        Checks the system's memory usage and updates the health status accordingly.
        Retrieves the current memory usage statistics using psutil, compares the usage percentage
        against configured warning and critical thresholds, and sets the memory status to 'healthy',
        'warning', or 'critical'. Updates the health_data dictionary with total memory, available memory,
        usage percentage, and status.
        
        Returns:
        
            None
        """
        
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        warning_threshold = self.config["thresholds"].get("memory_warning", 70)
        critical_threshold = self.config["thresholds"].get("memory_critical", 90)
        
        status = "healthy"
        if memory_percent >= critical_threshold:
            status = "critical"
        elif memory_percent >= warning_threshold:
            status = "warning"
            
        self.health_data["system"]["memory"] = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "usage_percent": memory_percent,
            "status": status
        }
        
    def check_disk(self):
        """
        Checks the disk usage of the root filesystem and updates the health status.
        Retrieves disk usage statistics using psutil, compares the usage percentage
        against configured warning and critical thresholds, and sets the disk status
        accordingly (`healthy`, `warning`, or `critical`). Updates the health_data
        dictionary with total disk size, free space, usage percentage, and status.
        
        Returns:
        
            None
        """
        
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        warning_threshold = self.config["thresholds"].get("disk_warning", 70)
        critical_threshold = self.config["thresholds"].get("disk_critical", 90)
        
        status = "healthy"
        if disk_percent >= critical_threshold:
            status = "critical"
        elif disk_percent >= warning_threshold:
            status = "warning"
            
        self.health_data["system"]["disk"] = {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "usage_percent": disk_percent,
            "status": status
        }
        
    def check_dependencies(self):
        """
        Checks the health of configured dependencies, including API endpoints and databases.
        Iterates through the list of API endpoints and databases specified in the configuration,
        and performs health checks on each by invoking the corresponding internal methods.
        
        Raises:
        
            Exception: If any dependency check fails.
        """
        
        # Check API endpoints
        for endpoint in self.config["dependencies"].get("api_endpoints", []):
            self._check_api_endpoint(endpoint)
            
        # Check database connections
        for db in self.config["dependencies"].get("databases", []):
            self._check_database(db)
            
    def _check_api_endpoint(self, endpoint: Dict):
        """
        Check if an API endpoint is accessible.
        
        Args:
        
            endpoint: Dictionary with endpoint configuration
        """
        name = endpoint.get("name", "unknown_api")
        url = endpoint.get("url", "")
        timeout = endpoint.get("timeout", 5)
        
        if not url:
            return
            
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            response_time = time.time() - start_time
            
            status = "healthy" if response.status_code < 400 else "critical"
            
            self.health_data["dependencies"][name] = {
                "type": "api",
                "url": url,
                "status": status,
                "response_time_ms": round(response_time * 1000, 2),
                "status_code": response.status_code
            }
        except Exception as e:
            self.health_data["dependencies"][name] = {
                "type": "api",
                "url": url,
                "status": "critical",
                "error": str(e)
            }
            
    def _check_database(self, db_config: Dict):
        """
        Check database connection.
        Note: This is a placeholder. You'll need to implement specific database checks
        based on your application's needs.
        
        Args:
        
            db_config: Dictionary with database configuration
        """
        name = db_config.get("name", "unknown_db")
        db_type = db_config.get("type", "")
        
        # Placeholder for database connection check
        # In a real implementation, you would check the specific database connection
        self.health_data["dependencies"][name] = {
            "type": "database",
            "db_type": db_type,
            "status": "unknown",
            "message": "Database check not implemented"
        }
        
    def register_custom_check(self, name: str, check_func: Callable[[], Dict[str, Any]]):
        """
        Register a custom health check function.
        
        Args:
        
            name: Name of the custom check
            check_func: Function that performs the check and returns a dictionary with results
        """
        if "custom_checks" not in self.health_data:
            self.health_data["custom_checks"] = {}
            
        self.health_data["custom_checks"][name] = {
            "status": "unknown",
            "check_func": check_func
        }
        
    def run_custom_checks(self):
        """Run all registered custom health checks."""
        if "custom_checks" not in self.health_data:
            return
            
        for name, check_info in list(self.health_data["custom_checks"].items()):
            if "check_func" in check_info and callable(check_info["check_func"]):
                try:
                    result = check_info["check_func"]()
                    # Remove the function reference from the result
                    func = check_info["check_func"]
                    self.health_data["custom_checks"][name] = result
                    # Add the function back
                    self.health_data["custom_checks"][name]["check_func"] = func
                except Exception as e:
                    self.health_data["custom_checks"][name] = {
                        "status": "critical",
                        "error": str(e),
                        "check_func": check_info["check_func"]
                    }
                    
    def _update_overall_status(self):
        """
        Updates the overall health status of the application based on the statuses of various components.
        
        The method checks the health status of the following components:
            - Streamlit server
            - System checks
            - Dependencies
            - Custom checks (excluding those with a 'check_func' key)
            - Streamlit pages
            
        The overall status is determined using the following priority order:
            1. "critical" if any component is critical
            2. "warning" if any component is warning and none are critical
            3. "unknown" if any component is unknown and none are critical or warning, and no healthy components exist
            4. "healthy" if any component is healthy and none are critical, warning, or unknown
            5. "unknown" if no statuses are found
            
        The result is stored in `self.health_data["overall_status"]`.
        """
        
        has_critical = False
        has_warning = False
        has_healthy = False
        has_unknown = False
        
        # Helper function to check status
        def check_component_status(status):
            nonlocal has_critical, has_warning, has_healthy, has_unknown
            if status == "critical":
                has_critical = True
            elif status == "warning":
                has_warning = True
            elif status == "healthy":
                has_healthy = True
            elif status == "unknown":
                has_unknown = True

        # Check Streamlit server status
        server_status = self.health_data.get("streamlit_server", {}).get("status")
        check_component_status(server_status)
        
        # Check system status
        for system_check in self.health_data.get("system", {}).values():
            check_component_status(system_check.get("status"))
                    
        # Check dependencies status
        for dep_check in self.health_data.get("dependencies", {}).values():
            check_component_status(dep_check.get("status"))
                    
        # Check custom checks status
        for custom_check in self.health_data.get("custom_checks", {}).values():
            if isinstance(custom_check, dict) and "check_func" not in custom_check:
                check_component_status(custom_check.get("status"))
        
        # Check Streamlit pages status
        pages_status = self.health_data.get("streamlit_pages", {}).get("status")
        check_component_status(pages_status)
                        
        # Determine overall status with priority:
        # critical > warning > unknown > healthy
        if has_critical:
            self.health_data["overall_status"] = "critical"
        elif has_warning:
            self.health_data["overall_status"] = "warning"
        elif has_unknown and not has_healthy:
            self.health_data["overall_status"] = "unknown"
        elif has_healthy:
            self.health_data["overall_status"] = "healthy"
        else:
            self.health_data["overall_status"] = "unknown"
                
    def get_health_data(self) -> Dict:
        """Get the latest health check data."""
        # Create a copy without the function references
        result: Dict[str, Any] = {}
        for key, value in self.health_data.items():
            if key == "custom_checks":
                result[key] = {}
                for check_name, check_data in value.items():
                    if isinstance(check_data, dict):
                        check_copy = check_data.copy()
                        if "check_func" in check_copy:
                            del check_copy["check_func"]
                        result[key][check_name] = check_copy
            else:
                result[key] = value
        return result
        
    def save_config(self):
        """
        Saves the current health check configuration to a JSON file.
        Attempts to write the configuration stored in `self.config` to the file specified by `self.config_path`.
        Displays a success message in the Streamlit app upon successful save.
        Handles and displays appropriate error messages for file not found, permission issues, JSON decoding errors, and other exceptions.
        
        Raises:
        
            FileNotFoundError: If the configuration file path does not exist.
            PermissionError: If there are insufficient permissions to write to the file.
            json.JSONDecodeError: If there is an error decoding the JSON data.
            Exception: For any other exceptions encountered during the save process.
        """
        
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
                st.success(f"Health check config saved successfully to {self.config_path}")
        except FileNotFoundError:
            st.error(f"Configuration file not found: {self.config_path}")
        except PermissionError:
            st.error(f"Permission denied: Unable to write to {self.config_path}")
        except json.JSONDecodeError:
            st.error(f"Error decoding JSON in config file: {self.config_path}")
        except Exception as e:
            st.error(f"Error saving health check config: {str(e)}")
    def check_streamlit_pages(self):
        """
        Checks for errors in Streamlit pages and updates the health data accordingly.
        This method retrieves page errors using StreamlitPageMonitor.get_page_errors().
        If errors are found, it sets the 'streamlit_pages' status to 'critical' and updates
        the overall health status to 'critical'. If no errors are found, it marks the
        'streamlit_pages' status as 'healthy'.
        
        Updates:
        
            self.health_data["streamlit_pages"]: Dict containing status, error count, errors, and details.
            self.health_data["overall_status"]: Set to 'critical' if errors are detected.
            self.health_data["streamlit_pages"]["details"]: A summary of the errors found.
            
        Returns:
        
            None
        """
        
        page_errors = StreamlitPageMonitor.get_page_errors()
        
        if "streamlit_pages" not in self.health_data:
            self.health_data["streamlit_pages"] = {}
        
        if page_errors:
            total_errors = sum(len(errors) for errors in page_errors.values())
            self.health_data["streamlit_pages"] = {
                "status": "critical",
                "error_count": total_errors,
                "errors": page_errors,
                "details": "Errors detected in Streamlit pages"
            }
            # This affects overall status
            self.health_data["overall_status"] = "critical"
        else:
            self.health_data["streamlit_pages"] = {
                "status": "healthy",
                "error_count": 0,
                "errors": {},
                "details": "All pages functioning normally"
            }
    
    def check_streamlit_server(self) -> Dict[str, Any]:
        """
        Checks the health status of the Streamlit server by sending a GET request to the /healthz endpoint.
        
        Returns:
        
            Dict[str, Any]: A dictionary containing the health status, response code, latency in milliseconds,
                            message, and the URL checked. If the server is healthy (HTTP 200), status is "healthy".
                            Otherwise, status is "critical" with error details.
                            
        Handles:
        
            - Connection errors: Returns critical status with connection error details.
            - Timeout errors: Returns critical status with timeout error details.
            - Other exceptions: Returns critical status with unknown error details.
            
        Logs:
        
            - The URL being checked.
            - The response status code and text.
            - Health status and response time if healthy.
            - Warnings and errors for unhealthy or failed checks.
        """
        
        try:
            host = self.streamlit_url.rstrip('/')
            if not host.startswith(('http://', 'https://')):
                host = f"http://{host}"
            
            url = f"{host}:{self.streamlit_port}/healthz"
            self.logger.info(f"Checking Streamlit server health at: {url}")
            
            start_time = time.time()
            response = requests.get(url, timeout=3)
            total_time = (time.time() - start_time) * 1000
            self.logger.info(f"{response.status_code} - {response.text}")
            # Check if the response is healthy
            if response.status_code == 200:
                self.logger.info(f"Streamlit server healthy - Response time: {round(total_time, 2)}ms")
                return {
                    "status": "healthy",
                    "response_code": response.status_code,
                    "latency_ms": round(total_time, 2),
                    "message": "Streamlit server is running",
                    "url": url
                }
            else:
                self.logger.warning(f"Unhealthy response from server: {response.status_code}")
                return {
                    "status": "critical",
                    "response_code": response.status_code,
                    "error": f"Unhealthy response from server: {response.status_code}",
                    "message": "Streamlit server is not healthy",
                    "url": url
                }

        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error while checking Streamlit server: {str(e)}")
            return {
                "status": "critical",
                "error": f"Connection error: {str(e)}",
                "message": "Cannot connect to Streamlit server",
                "url": url
            }
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout while checking Streamlit server: {str(e)}")
            return {
                "status": "critical",
                "error": f"Timeout error: {str(e)}",
                "message": "Streamlit server is not responding",
                "url": url
            }
        except Exception as e:
            self.logger.error(f"Unexpected error while checking Streamlit server: {str(e)}")
            return {
                "status": "critical",
                "error": f"Unknown error: {str(e)}",
                "message": "Failed to check Streamlit server",
                "url": url
            }
    
def health_check(config_path:str = "health_check_config.json"):
    """
    Displays an interactive Streamlit dashboard for monitoring application health.
    This function initializes and manages a health check service, presenting real-time system metrics,
    dependency statuses, custom checks, and Streamlit page health in a user-friendly dashboard.
    Users can manually refresh health checks, view detailed error information, and adjust configuration
    thresholds and intervals directly from the UI.
    
    Args:
    
        config_path (str, optional): Path to the health check configuration JSON file.
            Defaults to "health_check_config.json".
            
    Features:
    
        - Displays overall health status with color-coded indicators.
        - Shows last updated timestamp for health data.
        - Monitors Streamlit server status, latency, and errors.
        - Provides tabs for:
            * System Resources (CPU, Memory, Disk usage and status)
            * Dependencies (external services and their health)
            * Custom Checks (user-defined health checks)
            * Streamlit Pages (page-specific errors and status)
        - Allows configuration of system thresholds, check intervals, and Streamlit server settings.
        - Supports manual refresh and saving configuration changes.
        
    Raises:
    
        Displays error messages in the UI for any exceptions encountered during health data retrieval or processing.
        
    Returns:
    
        None. The dashboard is rendered in the Streamlit app.
    """
    
    logger = logging.getLogger(f"{__name__}.health_check")
    logger.info("Starting health check dashboard")
    st.title("Application Health Dashboard")
    
    # Initialize or get the health check service
    if "health_service" not in st.session_state:
        logger.info("Initializing new health check service")
        st.session_state.health_service = HealthCheckService(config_path = config_path)
        st.session_state.health_service.start()
    
    health_service = st.session_state.health_service
    health_service.run_all_checks()
    
    # Add controls for manual refresh and configuration
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("System Health Status")
    with col2:
        if st.button("Refresh Now"):
            health_service.run_all_checks()
    
    # Get the latest health data
    health_data = health_service.get_health_data()
    
    # Display overall status with appropriate color
    overall_status = health_data.get("overall_status", "unknown")
    status_color = {
        "healthy": "green",
        "warning": "orange",
        "critical": "red",
        "unknown": "gray"
    }.get(overall_status, "gray")
    
    st.markdown(
        f"<h3 style='color: {status_color};'>Overall Status: {overall_status.upper()}</h3>",
        unsafe_allow_html=True
    )
    
    # Display last updated time
    if health_data.get("last_updated"):
        try:
            last_updated = datetime.fromisoformat(health_data["last_updated"])
            st.text(f"Last updated: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        except Exception as e:
            st.error(f"Last updated: {health_data['last_updated']}")
            st.exception(e)
    
    server_health = health_data.get("streamlit_server", {})
    server_status = server_health.get("status", "unknown")
    server_color = {
        "healthy": "green",
        "critical": "red",
        "unknown": "gray"
    }.get(server_status, "gray")

    st.markdown(
        f"### Streamlit Server Status: <span style='color: {server_color}'>{server_status.upper()}</span>",
        unsafe_allow_html=True
    )

    if server_status != "healthy":
        st.error(server_health.get("message", "Server status unknown"))
        if "error" in server_health:
            st.code(server_health["error"])
    else:
        st.success(server_health.get("message", "Server is running"))
        if "latency_ms" in server_health:
            latency = server_health["latency_ms"]
            # Define color based on latency thresholds
            if latency <= 50:
                latency_color = "green"
                performance = "Excellent"
            elif latency <= 100:
                latency_color = "blue"
                performance = "Good"
            elif latency <= 200:
                latency_color = "orange"
                performance = "Fair"
            else:
                latency_color = "red"
                performance = "Poor"
                
            st.markdown(
                f"""
                <div style='display: flex; align-items: center; gap: 10px;'>
                    <div>Server Response Time:</div>
                    <div style='color: {latency_color}; font-weight: bold;'>
                        {latency} ms
                    </div>
                    <div style='color: {latency_color};'>
                        ({performance})
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    
    # Create tabs for different categories of health checks
    tab1, tab2, tab3, tab4 = st.tabs(["System Resources", "Dependencies", "Custom Checks", "Streamlit Pages"])
    
    with tab1:
        # Display system health checks
        system_data = health_data.get("system", {})
        
        # CPU
        if "cpu" in system_data:
            cpu_data = system_data["cpu"]
            cpu_status = cpu_data.get("status", "unknown")
            cpu_color = {"healthy": "green", "warning": "orange", "critical": "red"}.get(cpu_status, "gray")
            
            st.markdown(f"### CPU Status: <span style='color:{cpu_color}'>{cpu_status.upper()}</span>", unsafe_allow_html=True)
            st.progress(cpu_data.get("usage_percent", 0) / 100)
            st.text(f"CPU Usage: {cpu_data.get('usage_percent', 0)}%")
        
        # Memory
        if "memory" in system_data:
            memory_data = system_data["memory"]
            memory_status = memory_data.get("status", "unknown")
            memory_color = {"healthy": "green", "warning": "orange", "critical": "red"}.get(memory_status, "gray")
            
            st.markdown(f"### Memory Status: <span style='color:{memory_color}'>{memory_status.upper()}</span>", unsafe_allow_html=True)
            st.progress(memory_data.get("usage_percent", 0) / 100)
            st.text(f"Memory Usage: {memory_data.get('usage_percent', 0)}%")
            st.text(f"Total Memory: {memory_data.get('total_gb', 0)} GB")
            st.text(f"Available Memory: {memory_data.get('available_gb', 0)} GB")
        
        # Disk
        if "disk" in system_data:
            disk_data = system_data["disk"]
            disk_status = disk_data.get("status", "unknown")
            disk_color = {"healthy": "green", "warning": "orange", "critical": "red"}.get(disk_status, "gray")
            
            st.markdown(f"### Disk Status: <span style='color:{disk_color}'>{disk_status.upper()}</span>", unsafe_allow_html=True)
            st.progress(disk_data.get("usage_percent", 0) / 100)
            st.text(f"Disk Usage: {disk_data.get('usage_percent', 0)}%")
            st.text(f"Total Disk Space: {disk_data.get('total_gb', 0)} GB")
            st.text(f"Free Disk Space: {disk_data.get('free_gb', 0)} GB")
    
    with tab2:
        # Display dependency health checks
        dependencies = health_data.get("dependencies", {})
        if dependencies:
            # Create a dataframe for all dependencies
            dep_data = []
            for name, dep_info in dependencies.items():
                dep_data.append({
                    "Name": name,
                    "Type": dep_info.get("type", "unknown"),
                    "Status": dep_info.get("status", "unknown"),
                    "Details": ", ".join([f"{k}: {v}" for k, v in dep_info.items() 
                               if k not in ["name", "type", "status", "error"] and not isinstance(v, dict)])
                })
            
            # Show dependencies table
            if dep_data:
                df_deps = pd.DataFrame(dep_data)
                st.dataframe(df_deps)
            else:
                st.info("No dependencies configured")

            # Create a dataframe for all custom checks from health_data
            custom_checks = health_data.get("custom_checks", {})
            check_data = []
            for name, check_info in custom_checks.items():
                if isinstance(check_info, dict) and "check_func" not in check_info:
                    check_data.append({
                        "Name": name,
                        "Status": check_info.get("status", "unknown"),
                        "Details": ", ".join([f"{k}: {v}" for k, v in check_info.items()
                                             if k not in ["name", "status", "check_func", "error"] and not isinstance(v, dict)]),
                        "Error": check_info.get("error", "")
                    })

            if check_data:
                df_checks = pd.DataFrame(check_data)

                # Apply color formatting to status column
                def color_status(val):
                    colors = {
                        "healthy": "background-color: #c6efce; color: #006100",
                        "warning": "background-color: #ffeb9c; color: #9c5700",
                        "critical": "background-color: #ffc7ce; color: #9c0006",
                        "unknown": "background-color: #eeeeee; color: #7f7f7f"
                    }
                    return colors.get(str(val).lower(), "")

                # Use styled dataframe to color the Status column
                try:
                    # apply expects a function that returns a sequence of styles for the column;
                    # map color_status across the 'Status' column to produce the CSS strings.
                    st.dataframe(
                        df_checks.style.apply(
                            lambda col: col.map(color_status),
                            subset=["Status"]
                        )
                    )
                except Exception:
                    # Fallback if styling isn't supported in the environment
                    st.dataframe(df_checks)
            else:
                st.info("No custom checks configured")
        else:
            st.info("No custom checks configured")
    with tab4:
        # Always read page errors from SQLite DB for latest state
        page_errors = StreamlitPageMonitor.get_page_errors()
        error_count = sum(len(errors) for errors in page_errors.values())
        status = "critical" if error_count > 0 else "healthy"
        status_color = {
            "healthy": "green",
            "critical": "red",
            "unknown": "gray"
        }.get(status, "gray")
        st.markdown(f"### Page Status: <span style='color:{status_color}'>{status.upper()}</span>", unsafe_allow_html=True)
        st.metric("Error Count", error_count)
        if error_count > 0:
            st.markdown("<div style='background-color:#ffe6e6; color:#b30000; padding:10px; border-radius:5px; border:1px solid #b30000; font-weight:bold;'>Pages with errors:</div>",
            unsafe_allow_html=True)
            for page_name, page_errors_list in page_errors.items():
                display_name = page_name.split("/")[-1] if "/" in page_name else page_name
                for error_info in page_errors_list:
                    if isinstance(error_info, dict):
                        with st.expander(f"Error in {display_name}"):
                            st.info(error_info.get('error', 'Unknown error'))
                            if error_info.get('type') == 'streamlit_error':
                                st.text("Type: Streamlit Error")
                            else:
                                st.text("Type: Exception")
                            st.text("Traceback:")
                            st.code("".join(error_info.get('traceback', ['No traceback available'])))
                            st.text(f"Timestamp: {error_info.get('timestamp', 'No timestamp')}")
    
    # Configuration section
    with st.expander("Health Check Configuration"):
        st.subheader("System Check Thresholds")
        
        col1, col2 = st.columns(2)
        with col1:
            cpu_warning = st.slider("CPU Warning Threshold (%)", 
                                min_value=10, max_value=90, 
                                value=health_service.config["thresholds"].get("cpu_warning", 70),
                                step=5)
            memory_warning = st.slider("Memory Warning Threshold (%)", 
                                   min_value=10, max_value=90, 
                                   value=health_service.config["thresholds"].get("memory_warning", 70),
                                   step=5)
            disk_warning = st.slider("Disk Warning Threshold (%)", 
                                 min_value=10, max_value=90, 
                                 value=health_service.config["thresholds"].get("disk_warning", 70),
                                 step=5)
            streamlit_url_update = st.text_input(
                "Streamlit Server URL",
                value=health_service.config.get("streamlit_url", "http://localhost")
            )
        
        with col2:
            cpu_critical = st.slider("CPU Critical Threshold (%)", 
                                 min_value=20, max_value=95, 
                                 value=health_service.config["thresholds"].get("cpu_critical", 90),
                                 step=5)
            memory_critical = st.slider("Memory Critical Threshold (%)", 
                                    min_value=20, max_value=95, 
                                    value=health_service.config["thresholds"].get("memory_critical", 90),
                                    step=5)
            disk_critical = st.slider("Disk Critical Threshold (%)", 
                                  min_value=20, max_value=95, 
                                  value=health_service.config["thresholds"].get("disk_critical", 90),
                                  step=5)
        
            check_interval = st.slider("Check Interval (seconds)", 
                                min_value=10, max_value=300, 
                                value=health_service.config.get("check_interval", 60),
                                step=10)
            streamlit_port_update = st.number_input(
                "Streamlit Server Port",
                value=health_service.config.get("streamlit_port", 8501),
                step=1
            )
        
        if st.button("Save Configuration"):
            # Update configuration
            health_service.config["thresholds"]["cpu_warning"] = cpu_warning
            health_service.config["thresholds"]["cpu_critical"] = cpu_critical
            health_service.config["thresholds"]["memory_warning"] = memory_warning
            health_service.config["thresholds"]["memory_critical"] = memory_critical
            health_service.config["thresholds"]["disk_warning"] = disk_warning
            health_service.config["thresholds"]["disk_critical"] = disk_critical
            health_service.config["check_interval"] = check_interval
            health_service.config["streamlit_url"] = streamlit_url_update
            health_service.config["streamlit_port"] = streamlit_port_update
            
            # Save to file
            health_service.save_config()
            st.success("Configuration saved successfully")
            
            # Restart the service if interval changed
            health_service.stop()
            health_service.start()
