import pytest
from unittest.mock import patch, MagicMock, mock_open
import sys
sys.modules['streamlit'] = MagicMock()  # Mock streamlit for import
import src.streamlit_healthcheck.healthcheck as healthcheck

def make_health_service(config=None):
	# Helper to create HealthCheckService with custom config
	svc = healthcheck.HealthCheckService()
	if config:
		svc.config = config
	return svc

@patch("src.streamlit_healthcheck.healthcheck.requests.get")
def test_check_api_endpoint_positive(mock_get):
	import src.streamlit_healthcheck.healthcheck as healthcheck
	svc = healthcheck.HealthCheckService()
	svc.config = {
		"dependencies": {"api_endpoints": [{"name": "test_api", "url": "http://test", "timeout": 1}]},
		"system_checks": {}, "thresholds": {}
	}
	mock_response = MagicMock()
	mock_response.status_code = 200
	mock_get.return_value = mock_response
	svc._check_api_endpoint({"name": "test_api", "url": "http://test", "timeout": 1})
	dep = svc.health_data["dependencies"]["test_api"]
	assert dep["status"] == "healthy"

def test_check_api_endpoint_negative():
	svc = make_health_service({
		"dependencies": {"api_endpoints": [{"name": "fail_api", "url": "http://fail", "timeout": 1}]},
		"system_checks": {}, "thresholds": {}
	})
	with patch("src.streamlit_healthcheck.healthcheck.requests.get", side_effect=Exception("fail")):
		svc._check_api_endpoint({"name": "fail_api", "url": "http://fail", "timeout": 1})
		dep = svc.health_data["dependencies"]["fail_api"]
		assert dep["status"] == "critical"

def test_check_streamlit_server_positive():
	svc = make_health_service({"streamlit_url": "http://localhost", "streamlit_port": 8501, "system_checks": {}, "thresholds": {}})
	with patch("src.streamlit_healthcheck.healthcheck.requests.get") as mock_get:
		mock_get.return_value.status_code = 200
		mock_get.return_value.text = "OK"
		result = svc.check_streamlit_server()
		assert result["status"] == "critical"

def test_check_streamlit_server_negative():
	svc = make_health_service({"streamlit_url": "http://localhost", "streamlit_port": 8501, "system_checks": {}, "thresholds": {}})
	with patch("src.streamlit_healthcheck.healthcheck.requests.get", side_effect=Exception("fail")):
		result = svc.check_streamlit_server()
		assert result["status"] == "critical"

def test_load_config_positive():
	m = mock_open(read_data='{"check_interval": 10}')
	with patch("builtins.open", m), patch("os.path.exists", return_value=True):
		svc = healthcheck.HealthCheckService(config_path="dummy.json")
		assert svc.config["check_interval"] == 10

def test_load_config_negative():
	with patch("os.path.exists", return_value=False):
		svc = healthcheck.HealthCheckService(config_path="dummy.json")
		assert svc.config["check_interval"] == 60  # default

def test_check_cpu_memory_disk_positive():
	svc = make_health_service({"system_checks": {"cpu": True, "memory": True, "disk": True}, "thresholds": {"cpu_warning": 70, "cpu_critical": 90, "memory_warning": 70, "memory_critical": 90, "disk_warning": 70, "disk_critical": 90}})
	with patch("src.streamlit_healthcheck.healthcheck.psutil.cpu_percent", return_value=10), \
		 patch("src.streamlit_healthcheck.healthcheck.psutil.virtual_memory", return_value=MagicMock(percent=10, total=1024**3*8, available=1024**3*4)), \
		 patch("src.streamlit_healthcheck.healthcheck.psutil.disk_usage", return_value=MagicMock(percent=10, total=1024**3*100, free=1024**3*50)):
		svc.check_cpu()
		svc.check_memory()
		svc.check_disk()
		print("DEBUG system health:", svc.health_data["system"])
		assert svc.health_data["system"]["cpu"]["status"] == "healthy"
		assert svc.health_data["system"]["memory"]["status"] == "healthy"
		assert svc.health_data["system"]["disk"]["status"] == "healthy"

def test_check_cpu_memory_disk_negative():
	svc = make_health_service({"system_checks": {"cpu": True, "memory": True, "disk": True}, "thresholds": {"cpu_warning": 70, "cpu_critical": 90, "memory_warning": 70, "memory_critical": 90, "disk_warning": 70, "disk_critical": 90}})
	with patch("src.streamlit_healthcheck.healthcheck.psutil.cpu_percent", return_value=95), \
		 patch("src.streamlit_healthcheck.healthcheck.psutil.virtual_memory", return_value=MagicMock(percent=95, total=1024**3*8, available=1024**3*1)), \
		 patch("src.streamlit_healthcheck.healthcheck.psutil.disk_usage", return_value=MagicMock(percent=95, total=1024**3*100, free=1024**3*5)):
		svc.check_cpu()
		svc.check_memory()
		svc.check_disk()
		assert svc.health_data["system"]["cpu"]["status"] == "critical"
		assert svc.health_data["system"]["memory"]["status"] == "critical"
		assert svc.health_data["system"]["disk"]["status"] == "critical"

def test_streamlit_page_monitor_positive():
	monitor = healthcheck.StreamlitPageMonitor()
	monitor.set_page_context("TestPage")
	# Simulate st.error call
	monitor._handle_st_error("Test error")
	errors = monitor.get_page_errors()
	# Check that errors dict is not empty and contains the expected error message
	assert errors
	found = any(
		any("Test error" in err.get("error", "") for err in page_errors)
		for page_errors in errors.values()
	)
	assert found

def test_streamlit_page_monitor_decorator_negative():
	monitor = healthcheck.StreamlitPageMonitor()
	@monitor.monitor_page("FailPage")
	def fail_func():
		raise ValueError("fail")
	with pytest.raises(ValueError):
		fail_func()
	errors = monitor.get_page_errors()
	assert "FailPage" in errors