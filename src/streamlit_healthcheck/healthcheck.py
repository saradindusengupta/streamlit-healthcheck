import streamlit as st
import psutil
import numpy as np
import pandas as pd
import requests
import time
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
import threading
import functools
import traceback

class StreamlitPageMonitor:
    """Monitor Streamlit pages for exceptions and st.error calls"""
    _instance = None
    _errors: Dict[str, List[Dict[str, Any]]] = {}  # Changed to store lists of errors
    _st_error = st.error  # Store original st.error

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StreamlitPageMonitor, cls).__new__(cls)
            # Monkey patch st.error to capture error messages
            def patched_error(*args, **kwargs):
                error_message = " ".join(str(arg) for arg in args)
                cls._handle_st_error(error_message)
                return cls._st_error(*args, **kwargs)
            st.error = patched_error
        return cls._instance

    @classmethod
    def _handle_st_error(cls, error_message: str):
        """Handle st.error calls and record them"""
        # Get current page name from Streamlit context
        current_page = getattr(st, '_current_page', 'unknown_page')
        
        error_info = {
            'error': f"Streamlit Error: {error_message}",
            'traceback': traceback.format_stack(),
            'timestamp': datetime.now().isoformat(),
            'status': 'critical',
            'type': 'streamlit_error'
        }

        # Initialize list for page if not exists
        if current_page not in cls._errors:
            cls._errors[current_page] = []

        # Add new error
        cls._errors[current_page].append(error_info)

    @classmethod
    def monitor_page(cls, page_name):
        """Decorator to monitor Streamlit pages for exceptions and st.error calls"""
        def decorator(func):
            @functools.wraps(func) 
            def wrapper(*args, **kwargs):
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
                        'type': 'exception'
                    }
                    
                    if page_name not in cls._errors:
                        cls._errors[page_name] = []
                    cls._errors[page_name].append(error_info)
                    raise
            return wrapper
        return decorator

    @classmethod
    def get_page_errors(cls):
        """Get all recorded page errors"""
        return {
            page: errors 
            for page, errors in cls._errors.items() 
            if errors  # Only return pages that have errors
        }

    @classmethod
    def clear_errors(cls, page_name: Optional[str] = None):
        """Clear errors for a specific page or all pages"""
        if page_name:
            if page_name in cls._errors:
                del cls._errors[page_name]
        else:
            cls._errors = {}

class HealthCheckService:
    """
    A health check service for Streamlit multi-page applications.
    Monitors system resources, external dependencies, and custom application checks.
    """
    
    def __init__(self, config_path: str = "health_check_config.json"):
        """
        Initialize the health check service.
        
        Args:
            config_path: Path to the health check configuration file
        """
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
            "system_checks": {
                "cpu": True,
                "memory": True,
                "disk": True
            },
            "dependencies": {
                "api_endpoints": [
                    {"name": "example_api", "url": "https://httpbin.org/get", "timeout": 5}
                ],
                "databases": [
                    # Example database connection to check
                    # {"name": "main_db", "type": "postgres", "connection_string": "..."}
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
        """Start the health check service in a background thread."""
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
        
        # System checks
        if self.config["system_checks"].get("cpu", True):
            self.check_cpu()
        if self.config["system_checks"].get("memory", True):
            self.check_memory()
        if self.config["system_checks"].get("disk", True):
            self.check_disk()
            
        # Dependency checks
        self.check_dependencies()
        
        # Custom checks (if any registered)
        self.run_custom_checks()
        
        # Determine overall status
        self._update_overall_status()
        
        # Checks for Streamlit pages
        self.check_streamlit_pages()
        
    def check_cpu(self):
        """Check CPU usage and update health data."""
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
        """Check memory usage and update health data."""
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
        """Check disk usage and update health data."""
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
        """Check external dependencies like APIs and databases."""
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
        """Update the overall health status based on individual checks."""
        has_critical = False
        has_warning = False
        has_unknown = False
        
        # Check system status
        for system_check in self.health_data.get("system", {}).values():
            if system_check.get("status") == "critical":
                has_critical = True
            elif system_check.get("status") == "warning":
                has_warning = True
            elif system_check.get("status") == "unknown":
                has_unknown = True
                
        # Check dependencies status
        for dep_check in self.health_data.get("dependencies", {}).values():
            if dep_check.get("status") == "critical":
                has_critical = True
            elif dep_check.get("status") == "warning":
                has_warning = True
            elif dep_check.get("status") == "unknown":
                has_unknown = True
                
        # Check custom checks status
        for custom_check in self.health_data.get("custom_checks", {}).values():
            if isinstance(custom_check, dict) and "check_func" not in custom_check:
                if custom_check.get("status") == "critical":
                    has_critical = True
                elif custom_check.get("status") == "warning":
                    has_warning = True
                elif custom_check.get("status") == "unknown":
                    has_unknown = True
                    
        # Determine overall status
        if has_critical:
            self.health_data["overall_status"] = "critical"
        elif has_warning:
            self.health_data["overall_status"] = "warning"
        elif has_unknown:
            self.health_data["overall_status"] = "unknown"
        else:
            self.health_data["overall_status"] = "healthy"
            
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
        """Save the current configuration to file."""
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            st.error(f"Error saving health check config: {str(e)}")
    def check_streamlit_pages(self):
        """Check for any Streamlit page errors"""
        page_errors = StreamlitPageMonitor.get_page_errors()
        
        if "streamlit_pages" not in self.health_data:
            self.health_data["streamlit_pages"] = {}
        
        if page_errors:
            self.health_data["streamlit_pages"] = {
                "status": "critical",
                "error_count": len(page_errors),
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

def health_check():
    st.title("Application Health Dashboard")
    
    # Initialize or get the health check service
    if "health_service" not in st.session_state:
        st.session_state.health_service = HealthCheckService()
        st.session_state.health_service.start()
    
    health_service = st.session_state.health_service
    
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
        except:
            st.text(f"Last updated: {health_data['last_updated']}")
    
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
            
            if dep_data:
                df = pd.DataFrame(dep_data)
                
                # Apply color formatting to status column
                def color_status(val):
                    colors = {
                        "healthy": "background-color: #c6efce; color: #006100",
                        "warning": "background-color: #ffeb9c; color: #9c5700",
                        "critical": "background-color: #ffc7ce; color: #9c0006",
                        "unknown": "background-color: #eeeeee; color: #7f7f7f"
                    }
                    return colors.get(val.lower(), "")
                
                st.dataframe(df.style.map(color_status, subset=["Status"]))
            else:
                st.info("No dependencies configured")
        else:
            st.info("No dependencies configured")
    
    with tab3:
        # Display custom checks
        custom_checks = health_data.get("custom_checks", {})
        if custom_checks:
            # Create a dataframe for all custom checks
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
                df = pd.DataFrame(check_data)
                
                # Apply color formatting to status column
                def color_status(val):
                    colors = {
                        "healthy": "background-color: #c6efce; color: #006100",
                        "warning": "background-color: #ffeb9c; color: #9c5700",
                        "critical": "background-color: #ffc7ce; color: #9c0006",
                        "unknown": "background-color: #eeeeee; color: #7f7f7f"
                    }
                    return colors.get(val.lower(), "")
                
                st.dataframe(df.style.map(color_status, subset=["Status"]))
            else:
                st.info("No custom checks configured")
        else:
            st.info("No custom checks configured")
    with tab4:
        page_health = health_data.get("streamlit_pages", {})
        status = page_health.get("status", "unknown")
        error_count = page_health.get("error_count", 0)
        
        status_color = {
            "healthy": "green",
            "critical": "red",
            "unknown": "gray"
        }.get(status, "gray")
        
        st.markdown(f"### Page Status: <span style='color:{status_color}'>{status.upper()}</span>", unsafe_allow_html=True)
        st.metric("Error Count", error_count)
        
        if error_count > 0:
            st.error("Pages with errors:")
            errors_dict = page_health.get("errors", {})
            
            if not isinstance(errors_dict, dict):
                st.error("Invalid error data format")
                return
                
            for page_name, page_errors in errors_dict.items():
                # Ensure page_errors is a list
                if isinstance(page_errors, dict):
                    page_errors = [page_errors]
                elif not isinstance(page_errors, list):
                    continue
                    
                for error_info in page_errors:
                    if isinstance(error_info, dict):
                        with st.expander(f"Error in {page_name}"):
                            st.text(f"Error: {error_info.get('error', 'Unknown error')}")
                            st.text("Traceback:")
                            st.code(error_info.get('traceback', 'No traceback available'))
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
        
        if st.button("Save Configuration"):
            # Update configuration
            health_service.config["thresholds"]["cpu_warning"] = cpu_warning
            health_service.config["thresholds"]["cpu_critical"] = cpu_critical
            health_service.config["thresholds"]["memory_warning"] = memory_warning
            health_service.config["thresholds"]["memory_critical"] = memory_critical
            health_service.config["thresholds"]["disk_warning"] = disk_warning
            health_service.config["thresholds"]["disk_critical"] = disk_critical
            health_service.config["check_interval"] = check_interval
            
            # Save to file
            health_service.save_config()
            st.success("Configuration saved successfully")
            
            # Restart the service if interval changed
            health_service.stop()
            health_service.start()
