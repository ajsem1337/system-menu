import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / "system-menu/desktop-launch.py"
SPEC = importlib.util.spec_from_file_location("desktop_launch", PATH)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class DesktopLaunchTests(unittest.TestCase):
    def test_native_launch_is_not_attached_to_capture_pipes_or_timeout_group(self):
        with patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(launcher.main(["org.example.App.desktop"]), 0)
        run.assert_called_once_with(["gtk-launch", "org.example.App.desktop"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True,
                                    timeout=15, check=False)

    def test_native_failure_is_reported_without_fallback(self):
        with patch.object(launcher.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertEqual(launcher.main(["org.example.Missing.desktop"]), 1)
        run.assert_called_once()

    def test_missing_tools_and_timeout_return_failure(self):
        for error in (OSError("missing"), subprocess.TimeoutExpired("gtk-launch", 15)):
            with self.subTest(error=error), patch.object(launcher.subprocess, "run", side_effect=error) as run:
                self.assertEqual(launcher.main(["org.example.App.desktop"]), 1)
            run.assert_called_once()

    def test_invalid_ids_do_not_execute_anything(self):
        for argv in ([], ["--help"], ["/tmp/app.desktop"], ["a desktop"], ["bad\n.desktop"], ["app.desktop", "extra"]):
            with self.subTest(argv=argv), patch.object(launcher.subprocess, "run") as run:
                self.assertEqual(launcher.main(argv), 2)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
