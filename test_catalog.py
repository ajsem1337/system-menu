from pathlib import Path
import tomllib
import unittest


class CatalogTests(unittest.TestCase):
    def test_git_catalog_matches_plugin_manifest(self):
        root = Path(__file__).resolve().parent
        catalog = tomllib.loads((root / "catalog.toml").read_text())["plugin"]
        self.assertEqual(len(catalog), 1)
        entry = catalog[0]
        manifest_path = root / entry["id"].split("/", 1)[1] / "plugin.toml"
        manifest = tomllib.loads(manifest_path.read_text())
        for key in ("id", "name", "version", "plugin_api", "author", "license", "description", "icon", "tags", "dependencies"):
            with self.subTest(key=key):
                self.assertEqual(entry[key], manifest[key])


if __name__ == "__main__":
    unittest.main()
