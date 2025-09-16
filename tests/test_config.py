from pathlib import Path
from unittest.mock import patch


def test_settings_defaults(monkeypatch):
    """Test that settings have correct default values."""
    with patch("os.path.isfile", return_value=True):
        from takeout_automation.config import Settings

        test_settings = Settings()
        assert isinstance(test_settings.download_path, Path)
        assert test_settings.download_path == Path("./takeout-downloads")
        assert test_settings.executable_path is None


def test_settings_from_env(monkeypatch):
    """Test that settings can be loaded from environment variables."""
    monkeypatch.setenv("EXECUTABLE_PATH", "/path/to/brave")
    monkeypatch.setenv("DOWNLOAD_PATH", "/tmp/test")

    with patch("os.path.isfile", return_value=True):
        # Reload settings
        from takeout_automation.config import Settings

        test_settings = Settings()

        assert test_settings.download_path == Path("/tmp/test")
        assert test_settings.executable_path == "/path/to/brave"
