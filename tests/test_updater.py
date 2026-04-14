import time
from unittest.mock import patch


class TestIsNewer:
    """Test version comparison logic."""

    def test_newer_patch(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("0.1.2", "0.1.1") is True

    def test_newer_minor(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("0.2.0", "0.1.9") is True

    def test_newer_major(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("1.0.0", "0.9.9") is True

    def test_same_version(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("0.1.1", "0.1.1") is False

    def test_older_version(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("0.1.0", "0.1.1") is False

    def test_invalid_version_string(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("abc", "0.1.0") is False
        assert _is_newer("0.1.0", "xyz") is False

    def test_two_part_version(self):
        from dualentry_cli.updater import _is_newer

        assert _is_newer("0.2", "0.1") is True
        assert _is_newer("0.1", "0.2") is False


class TestCache:
    """Test cache read/write using a temp directory."""

    def test_read_empty_cache(self, tmp_path):
        from dualentry_cli.updater import _read_cache

        with patch("dualentry_cli.updater._UPDATE_CACHE", tmp_path / "nonexistent.json"):
            assert _read_cache() == {}

    def test_write_and_read_cache(self, tmp_path):
        from dualentry_cli.updater import _read_cache, _write_cache

        cache_file = tmp_path / ".update_check.json"
        with (
            patch("dualentry_cli.updater._UPDATE_CACHE", cache_file),
            patch("dualentry_cli.updater._CACHE_DIR", tmp_path),
        ):
            _write_cache({"last_check": 1000, "latest_version": "0.2.0"})
            result = _read_cache()
            assert result["latest_version"] == "0.2.0"
            assert result["last_check"] == 1000

    def test_read_corrupt_cache(self, tmp_path):
        from dualentry_cli.updater import _read_cache

        cache_file = tmp_path / ".update_check.json"
        cache_file.write_text("not valid json{{{")
        with patch("dualentry_cli.updater._UPDATE_CACHE", cache_file):
            assert _read_cache() == {}


class TestCheckForUpdates:
    """Test the update notification flow."""

    def test_shows_warning_when_outdated(self, capsys):
        from dualentry_cli.updater import check_for_updates

        cache = {"latest_version": "99.0.0", "last_check": time.time()}
        with (
            patch("dualentry_cli.updater._read_cache", return_value=cache),
            patch("dualentry_cli.updater.__version__", "0.1.0"),
        ):
            check_for_updates()
        captured = capsys.readouterr()
        assert "Update available" in captured.err
        assert "99.0.0" in captured.err
        assert "brew upgrade" in captured.err

    def test_no_warning_when_current(self, capsys):
        from dualentry_cli.updater import check_for_updates

        cache = {"latest_version": "0.1.0", "last_check": time.time()}
        with (
            patch("dualentry_cli.updater._read_cache", return_value=cache),
            patch("dualentry_cli.updater.__version__", "0.1.0"),
        ):
            check_for_updates()
        captured = capsys.readouterr()
        assert "Update available" not in captured.err

    def test_no_warning_when_no_cache(self, capsys):
        from dualentry_cli.updater import check_for_updates

        with patch("dualentry_cli.updater._read_cache", return_value={}):
            check_for_updates()
        captured = capsys.readouterr()
        assert "Update available" not in captured.err

    def test_refreshes_stale_cache(self):
        from dualentry_cli.updater import check_for_updates

        stale_cache = {"latest_version": "0.1.0", "last_check": 0}
        with (
            patch("dualentry_cli.updater._read_cache", return_value=stale_cache),
            patch("dualentry_cli.updater.__version__", "0.1.0"),
            patch("dualentry_cli.updater._refresh_update_cache") as mock_refresh,
            patch("threading.Thread") as mock_thread,
        ):
            check_for_updates()
            mock_thread.assert_called_once()

    def test_skips_refresh_when_fresh(self):
        from dualentry_cli.updater import check_for_updates

        fresh_cache = {"latest_version": "0.1.0", "last_check": time.time()}
        with (
            patch("dualentry_cli.updater._read_cache", return_value=fresh_cache),
            patch("dualentry_cli.updater.__version__", "0.1.0"),
            patch("threading.Thread") as mock_thread,
        ):
            check_for_updates()
            mock_thread.assert_not_called()
