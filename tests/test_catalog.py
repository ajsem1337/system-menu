from pathlib import Path
import json
import re
import tomllib
import unittest


class CatalogTests(unittest.TestCase):
    def test_task_manager_uses_mission_center_dependency(self):
        plugin = Path(__file__).resolve().parents[1] / "system-menu"
        manifest = tomllib.loads((plugin / "plugin.toml").read_text())
        self.assertIn("missioncenter", manifest["dependencies"])
        self.assertNotIn("btop", manifest["dependencies"])

    def test_git_catalog_matches_plugin_manifest(self):
        root = Path(__file__).resolve().parents[1]
        catalog = tomllib.loads((root / "catalog.toml").read_text())["plugin"]
        self.assertEqual(len(catalog), 1)
        entry = catalog[0]
        manifest_path = root / entry["id"].split("/", 1)[1] / "plugin.toml"
        manifest = tomllib.loads(manifest_path.read_text())
        for key in ("id", "name", "version", "plugin_api", "author", "license", "description", "icon", "tags", "dependencies"):
            with self.subTest(key=key):
                self.assertEqual(entry[key], manifest[key])

    def test_settings_translations_are_nested_and_documented(self):
        plugin = Path(__file__).resolve().parents[1] / "system-menu"
        manifest = tomllib.loads((plugin / "plugin.toml").read_text())
        translations = json.loads((plugin / "translations/en.json").read_text())

        def check_keys(node):
            for key, value in node.items():
                self.assertRegex(key, r"^[a-z0-9][a-z0-9_-]*$")
                if isinstance(value, dict):
                    check_keys(value)

        check_keys(translations)
        for setting in manifest["setting"]:
            for field in ("label_key", "description_key"):
                value = translations
                for segment in setting[field].split("."):
                    value = value[segment]
                self.assertIsInstance(value, str)
                self.assertTrue(value)
        self.assertRegex((plugin / "README.md").read_text(), re.compile(r"^## Settings$", re.MULTILINE))

    def test_argument_lists_have_a_plugin_local_visibility_switch(self):
        plugin = Path(__file__).resolve().parents[1] / "system-menu"
        manifest = tomllib.loads((plugin / "plugin.toml").read_text())
        settings = manifest["setting"]
        self.assertEqual([setting["key"] for setting in settings],
                         ["terminal", "aur_helper", "show_terminal_arguments", "terminal_args", "terminal_exec_args"])
        for setting, default in zip(settings[:2], ["kitty", "paru"]):
            self.assertEqual(setting["type"], "string")
            self.assertEqual(setting["default"], default)
            self.assertFalse(setting.get("advanced", False))
        toggle = settings[2]
        self.assertEqual(toggle["type"], "bool")
        self.assertIs(toggle["default"], False)
        self.assertFalse(toggle.get("advanced", False))
        for setting, default in zip(settings[3:], [[], ["-e"]]):
            self.assertEqual(setting["type"], "string_list")
            self.assertEqual(setting["default"], default)
            self.assertFalse(setting.get("advanced", False))
            self.assertEqual(setting["visible_when"],
                             {"key": toggle["key"], "values": ["true"]})

    def test_catalog_extra_tools_do_not_repeat_baseline_arch_commands(self):
        plugin = Path(__file__).resolve().parents[1] / "system-menu"
        manifest = tomllib.loads((plugin / "plugin.toml").read_text())
        baseline = {"pacman", "pacman-conf", "sudo", "lsblk", "cat"}
        self.assertFalse(baseline.intersection(manifest["dependencies"]))
        operations = (plugin / "OPERATIONS.md").read_text()
        for command in baseline:
            self.assertIn(f"`{command}`", operations)


if __name__ == "__main__":
    unittest.main()
