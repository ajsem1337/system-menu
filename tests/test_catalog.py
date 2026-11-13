from pathlib import Path
import json
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "system-menu"


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.manifest = tomllib.loads((PLUGIN / "plugin.toml").read_text())
        self.settings = {item["key"]: item for item in self.manifest["setting"]}

    def test_git_catalog_matches_plugin_manifest(self):
        catalog = tomllib.loads((ROOT / "catalog.toml").read_text())["plugin"]
        self.assertEqual(len(catalog), 1)
        for key, value in catalog[0].items():
            with self.subTest(key=key):
                self.assertEqual(value, self.manifest[key])

    def test_settings_translations_are_nested_and_documented(self):
        translations = json.loads((PLUGIN / "translations/en.json").read_text())

        def check_keys(node):
            for key, value in node.items():
                self.assertRegex(key, r"^[a-z0-9][a-z0-9_-]*$")
                if isinstance(value, dict):
                    check_keys(value)

        def translated(key):
            value = translations
            for segment in key.split("."):
                value = value[segment]
            self.assertIsInstance(value, str)
            self.assertTrue(value)

        check_keys(translations)
        for setting in self.settings.values():
            translated(setting["label_key"])
            translated(setting["description_key"])
            for option in setting.get("options", []):
                translated(option["label_key"])
        self.assertRegex((PLUGIN / "README.md").read_text(), re.compile(r"^## Settings$", re.MULTILINE))

    def test_launchers_do_not_require_a_specific_application(self):
        self.assertEqual(self.manifest["dependencies"], ["python3", "fastfetch"])
        self.assertNotIn("aur_helper", self.settings)
        for prefix in ("packages", "monitor"):
            self.assertEqual(self.settings[prefix + "_command"]["default"], "")
            self.assertEqual(self.settings[prefix + "_args"]["default"], [])
            mode = self.settings[prefix + "_mode"]
            self.assertEqual(mode["type"], "select")
            self.assertEqual({option["value"] for option in mode["options"]}, {"direct", "terminal", "desktop"})
            self.assertEqual(self.settings[prefix + "_args"]["visible_when"],
                             {"key": prefix + "_mode", "values": ["direct", "terminal"]})

    def test_terminal_argument_lists_keep_their_local_visibility_switch(self):
        self.assertEqual(self.settings["terminal"]["default"], "kitty")
        self.assertIs(self.settings["show_terminal_arguments"]["default"], False)
        for key, default in (("terminal_args", []), ("terminal_exec_args", ["-e"])):
            setting = self.settings[key]
            self.assertEqual(setting["type"], "string_list")
            self.assertEqual(setting["default"], default)
            self.assertEqual(setting["visible_when"], {"key": "show_terminal_arguments", "values": ["true"]})
        command_format = self.settings["terminal_command_format"]
        self.assertEqual(command_format["default"], "argv")
        self.assertEqual({option["value"] for option in command_format["options"]}, {"argv", "quoted"})
        self.assertEqual(command_format["visible_when"], {"key": "show_terminal_arguments", "values": ["true"]})

    def test_settings_are_grouped_terminal_packages_then_task_manager(self):
        self.assertEqual(list(self.settings), [
            "terminal", "show_terminal_arguments", "terminal_args", "terminal_exec_args", "terminal_command_format",
            "packages_mode", "packages_command", "packages_args",
            "monitor_mode", "monitor_command", "monitor_args",
        ])

    def test_readme_documents_all_settings_and_entries(self):
        readme = (PLUGIN / "README.md").read_text()
        for key in self.settings:
            self.assertIn(f"`{key}`", readme)
        for kind in ("widget", "panel"):
            for entry in self.manifest[kind]:
                self.assertIn(f"`{entry['id']}`", readme)

    def test_widget_does_not_bundle_or_invoke_the_package_frontend(self):
        self.assertFalse((PLUGIN / "packages/app.py").exists())
        sources = "\n".join(path.read_text() for path in PLUGIN.glob("*.luau"))
        for old_dependency in ("packages/app.py", "--aur-helper", "pacman", "sudo"):
            self.assertNotIn(old_dependency, sources)
        self.assertIn('"/plugin.toml"', (PLUGIN / "about.luau").read_text())


if __name__ == "__main__":
    unittest.main()
