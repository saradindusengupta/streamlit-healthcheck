
# Pytest version of the tests for StreamlitPageMonitor and HealthCheckService
import pytest
import tempfile
import os
import json
from unittest.mock import patch
import streamlit as st
from streamlit_healthcheck.healthcheck import StreamlitPageMonitor, HealthCheckService

# ------------------- StreamlitPageMonitor tests -------------------

@pytest.fixture(autouse=True)
def clear_monitor_errors():
    StreamlitPageMonitor.clear_errors()
    yield
    StreamlitPageMonitor.clear_errors()


@pytest.fixture
def temp_db_path():
    temp_db = tempfile.NamedTemporaryFile(delete=False)
    db_path = temp_db.name
    temp_db.close()
    # Reset singleton and set db_path, then init DB
    StreamlitPageMonitor._instance = None
    StreamlitPageMonitor._db_path = db_path
    StreamlitPageMonitor._init_db()
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_singleton(temp_db_path):
    m1 = StreamlitPageMonitor(db_path=temp_db_path)
    m2 = StreamlitPageMonitor()
    assert m1 is m2


def test_set_page_context(temp_db_path):
    StreamlitPageMonitor(db_path=temp_db_path)
    StreamlitPageMonitor.set_page_context("test_page")
    assert StreamlitPageMonitor._current_page == "test_page"


def test_handle_st_error_records_error(temp_db_path):
    StreamlitPageMonitor(db_path=temp_db_path)
    # Patch st._current_page so error is recorded under the right page
    st._current_page = "test_page"
    StreamlitPageMonitor.set_page_context("test_page")
    StreamlitPageMonitor._handle_st_error("Test error message")
    errors = StreamlitPageMonitor.get_page_errors()
    assert "test_page" in errors
    assert any("Test error message" in e["error"] for e in errors["test_page"])


def test_monitor_page_decorator_captures_exception(temp_db_path):
    StreamlitPageMonitor(db_path=temp_db_path)
    @StreamlitPageMonitor.monitor_page("decorator_page")
    def faulty():
        raise ValueError("Decorator error")
    with pytest.raises(ValueError):
        faulty()
    errors = StreamlitPageMonitor.get_page_errors()
    assert "decorator_page" in errors
    assert any("Decorator error" in e["error"] for e in errors["decorator_page"])


def test_save_and_load_errors_from_db(temp_db_path):
    StreamlitPageMonitor(db_path=temp_db_path)
    st._current_page = "db_page"
    StreamlitPageMonitor.set_page_context("db_page")
    StreamlitPageMonitor._handle_st_error("DB error")
    loaded = StreamlitPageMonitor.load_errors_from_db(page="db_page")
    assert any("DB error" in e["error"] for e in loaded)


def test_clear_errors(temp_db_path):
    StreamlitPageMonitor(db_path=temp_db_path)
    StreamlitPageMonitor.set_page_context("clear_page")
    StreamlitPageMonitor._handle_st_error("Clear error")
    StreamlitPageMonitor.clear_errors("clear_page")
    errors = StreamlitPageMonitor.get_page_errors()
    assert "clear_page" not in errors

# ------------------- HealthCheckService tests -------------------

@pytest.fixture
def temp_config_path():
    temp_config = tempfile.NamedTemporaryFile(delete=False, mode='w+')
    config = {
        "check_interval": 1,
        "streamlit_url": "http://localhost",
        "streamlit_port": 8501,
        "system_checks": {"cpu": True, "memory": True, "disk": True},
        "dependencies": {"api_endpoints": [], "databases": []},
        "thresholds": {
            "cpu_warning": 50, "cpu_critical": 90,
            "memory_warning": 50, "memory_critical": 90,
            "disk_warning": 50, "disk_critical": 90
        }
    }
    json.dump(config, temp_config)
    temp_config.close()
    yield temp_config.name
    if os.path.exists(temp_config.name):
        os.unlink(temp_config.name)

@pytest.fixture
def health_service(temp_config_path):
    return HealthCheckService(config_path=temp_config_path)

def test_load_config(health_service):
    assert health_service.config["check_interval"] == 1

def test_run_all_checks_populates_health_data(health_service):
    health_service.run_all_checks()
    assert "system" in health_service.health_data
    assert "overall_status" in health_service.health_data

def test_register_and_run_custom_check(health_service):
    def dummy_check():
        return {"status": "healthy", "detail": "ok"}
    health_service.register_custom_check("dummy", dummy_check)
    health_service.run_custom_checks()
    assert "dummy" in health_service.health_data["custom_checks"]
    assert health_service.health_data["custom_checks"]["dummy"]["status"] == "healthy"

@patch("psutil.cpu_percent", return_value=10)
def test_check_cpu_healthy(mock_cpu, health_service):
    health_service.check_cpu()
    assert health_service.health_data["system"]["cpu"]["status"] == "healthy"

@patch("psutil.virtual_memory")
def test_check_memory_warning(mock_vm, health_service):
    mock_vm.return_value.percent = 60
    health_service.config["thresholds"]["memory_warning"] = 50
    health_service.config["thresholds"]["memory_critical"] = 90
    health_service.check_memory()
    assert health_service.health_data["system"]["memory"]["status"] == "warning"

@patch("psutil.disk_usage")
def test_check_disk_critical(mock_du, health_service):
    mock_du.return_value.percent = 95
    health_service.config["thresholds"]["disk_critical"] = 90
    health_service.check_disk()
    assert health_service.health_data["system"]["disk"]["status"] == "critical"

def test_update_overall_status(health_service):
    health_service.health_data["system"] = {
        "cpu": {"status": "healthy"},
        "memory": {"status": "warning"},
        "disk": {"status": "healthy"}
    }
    health_service.health_data["dependencies"] = {}
    health_service.health_data["custom_checks"] = {}
    health_service._update_overall_status()
    assert health_service.health_data["overall_status"] == "warning"