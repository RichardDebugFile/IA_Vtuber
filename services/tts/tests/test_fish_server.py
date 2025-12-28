"""Unit tests for Fish Audio server manager."""
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from src.fish_server import FishServerManager, FishServerConfig


@pytest.fixture
def mock_config():
    """Mock configuration for Fish Audio server."""
    return FishServerConfig(
        repo_dir="/fake/repo",
        venv_python="/fake/venv/python.exe",
        ckpt_dir="/fake/checkpoint",
        host="127.0.0.1",
        port=8080,
        start_timeout=10
    )


@pytest.mark.unit
def test_fish_server_config_creation(mock_config):
    """Test that FishServerConfig can be created."""
    assert mock_config.repo_dir == "/fake/repo"
    assert mock_config.venv_python == "/fake/venv/python.exe"
    assert mock_config.ckpt_dir == "/fake/checkpoint"
    assert mock_config.host == "127.0.0.1"
    assert mock_config.port == 8080


@pytest.mark.unit
def test_fish_server_manager_init(mock_config):
    """Test FishServerManager initialization."""
    manager = FishServerManager(mock_config)
    assert manager.config == mock_config
    assert manager._proc is None


@pytest.mark.unit
@patch('src.fish_server.Path')
@patch('src.fish_server.subprocess.Popen')
def test_fish_server_start_when_not_running(mock_popen, mock_path, mock_config):
    """Test starting Fish server when it's not already running."""
    # Mock Path checks
    mock_path_instance = MagicMock()
    mock_path.return_value = mock_path_instance
    mock_path_instance.exists.return_value = True
    mock_path_instance.is_file.return_value = True

    # Mock subprocess
    mock_process = MagicMock()
    mock_process.pid = 1234
    mock_popen.return_value = mock_process

    manager = FishServerManager(mock_config)

    # Mock is_alive to return False initially, then True
    with patch.object(manager, 'is_alive', side_effect=[False, True]):
        with patch.object(manager, '_write_pid'):
            pid = manager.start()

    assert pid == 1234
    assert manager._proc == mock_process


@pytest.mark.unit
def test_fish_server_start_when_already_running(mock_config):
    """Test starting Fish server when it's already running."""
    manager = FishServerManager(mock_config)

    with patch.object(manager, 'is_alive', return_value=True):
        pid = manager.start()

    assert pid == -1  # Already running


@pytest.mark.unit
@patch('src.fish_server.httpx.get')
def test_fish_server_is_alive_healthy(mock_get, mock_config):
    """Test is_alive when server is healthy."""
    # Mock successful health check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    mock_get.return_value = mock_response

    manager = FishServerManager(mock_config)
    assert manager.is_alive() is True


@pytest.mark.unit
@patch('src.fish_server.httpx.get')
def test_fish_server_is_alive_unhealthy(mock_get, mock_config):
    """Test is_alive when server is not responding."""
    # Mock failed health check
    mock_get.side_effect = Exception("Connection refused")

    manager = FishServerManager(mock_config)
    assert manager.is_alive() is False


@pytest.mark.unit
def test_fish_server_stop_with_running_process(mock_config):
    """Test stopping a running Fish server."""
    manager = FishServerManager(mock_config)

    # Mock running process
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Still running
    manager._proc = mock_process

    with patch('src.fish_server.Path') as mock_path:
        mock_pid_file = MagicMock()
        mock_path.return_value = mock_pid_file

        manager.stop()

        # Should terminate the process
        mock_process.terminate.assert_called_once()


@pytest.mark.unit
@patch('src.fish_server.Path')
def test_fish_server_wait_ready_success(mock_path, mock_config):
    """Test wait_ready succeeds when server becomes healthy."""
    manager = FishServerManager(mock_config)

    # Mock is_alive to become True after first call
    with patch.object(manager, 'is_alive', side_effect=[False, False, True]):
        with patch('time.sleep'):  # Don't actually sleep in tests
            manager.wait_ready(timeout_s=5)
            # Should complete without exception


@pytest.mark.unit
def test_fish_server_wait_ready_timeout(mock_config):
    """Test wait_ready raises exception on timeout."""
    manager = FishServerManager(mock_config)

    # Mock is_alive to always return False
    with patch.object(manager, 'is_alive', return_value=False):
        with patch('time.sleep'):  # Don't actually sleep
            with pytest.raises(Exception, match="Health check timeout"):
                manager.wait_ready(timeout_s=1)


@pytest.mark.unit
def test_fish_server_validate_checkpoint_missing_files(mock_config):
    """Test checkpoint validation fails when files are missing."""
    with patch('src.fish_server.Path') as mock_path:
        # Mock missing codec.pth
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = False

        manager = FishServerManager(mock_config)

        with pytest.raises(FileNotFoundError):
            manager._validate_checkpoint()


@pytest.mark.unit
@patch.dict(os.environ, {"PYTORCH_CUDA_ALLOC_CONF": "max_split_size_mb=32;garbage_collection_threshold=0.7"})
def test_fish_server_normalize_cuda_conf(mock_config):
    """Test normalization of PYTORCH_CUDA_ALLOC_CONF."""
    manager = FishServerManager(mock_config)

    env = os.environ.copy()
    manager._normalize_cuda_conf(env)

    # Should convert = to : and ; to ,
    assert "max_split_size_mb:32,garbage_collection_threshold:0.7" in env.get("PYTORCH_CUDA_ALLOC_CONF", "")
