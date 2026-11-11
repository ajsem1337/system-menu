from pathlib import Path
import json
import re
import tomllib
import unittest


class CatalogTests(unittest.TestCase):
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

    def test_argument_lists_are_advanced_without_changing_keys_or_defaults(self):
        plugin = Path(__file__).resolve().parents[1] / "system-menu"
        manifest = tomllib.loads((plugin / "plugin.toml").read_text())
        settings = manifest["setting"]
        self.assertEqual([setting["key"] for setting in settings],
                         ["terminal", "aur_helper", "terminal_args", "terminal_exec_args"])
        for setting, default in zip(settings[:2], ["kitty", "paru"]):
            self.assertEqual(setting["type"], "string")
            self.assertEqual(setting["default"], default)
            self.assertFalse(setting.get("advanced", False))
        for setting, default in zip(settings[2:], [[], ["-e"]]):
            self.assertEqual(setting["type"], "string_list")
            self.assertEqual(setting["default"], default)
            self.assertTrue(setting["advanced"])


if __name__ == "__main__":
    unittest.main()
