"""Contract tests for the installable amoCRM ZIP, without touching live amoCRM."""

import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from validate_widget_zip import WidgetValidator


ROOT = Path(__file__).resolve().parent
RUNTIME = {
    "manifest.json", "script.js", "styles.css",
    "settings/settings.html", "settings/settings.js", "settings/settings.css",
    "i18n/ru.json", "i18n/en.json",
    "images/icon.png", "images/logo.png", "images/logo_main.png",
    "images/logo_medium.png", "images/logo_min.png", "images/logo_small.png",
    "images/tour_en.png", "images/tour_ru.png",
}


class WidgetPackageTests(unittest.TestCase):
    def make_zip(self, entries):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / "widget.zip"
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        return path

    def entries(self):
        result = {}
        for name in RUNTIME:
            source = ROOT / ("frontend" if name.startswith("settings/") else "widget") / name
            result[name] = source.read_bytes()
        return result

    def test_validator_rejects_missing_settings_asset(self):
        entries = self.entries()
        del entries["settings/settings.js"]
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(any("settings/settings.js" in error for error in validator.errors))

    def test_validator_rejects_extra_secret_or_source_map(self):
        for name in [".env", "settings/.env.production", "script.js.map", "frontend/admin.html"]:
            with self.subTest(name=name):
                entries = self.entries()
                entries[name] = b"dummy"
                validator = WidgetValidator(self.make_zip(entries))
                self.assertFalse(validator.validate())
                self.assertTrue(any(name in error for error in validator.errors))

    def test_validator_rejects_noncanonical_locations_and_invalid_utf8(self):
        entries = self.entries()
        manifest = json.loads(entries["manifest.json"])
        manifest["locations"] = ["advanced_settings", "settings", "dashboard"]
        entries["manifest.json"] = json.dumps(manifest).encode("utf-8")
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        entries = self.entries()
        entries["settings/settings.js"] = b"\xff"
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())

    def test_validator_rejects_credential_like_text(self):
        entries = self.entries()
        entries["settings/settings.html"] += b"\nBearer abcdefghijklmnopqrstuvwxyz123456\n"
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(any("Credential-like" in error for error in validator.errors))

    def test_validator_rejects_corrupt_required_image(self):
        entries = self.entries()
        entries["images/logo.png"] = b"not a PNG"
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(any("images/logo.png" in error for error in validator.errors))

    def test_builder_stages_exact_runtime_without_rewriting_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(ROOT / "frontend" / "settings", work / "frontend" / "settings")
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            locale = work / "widget" / "i18n" / "en.json"
            locale.write_bytes(b"\xef\xbb\xbf" + locale.read_bytes())
            before = {str(path.relative_to(work)): path.read_bytes()
                      for path in (work / "widget").rglob("*") if path.is_file()}
            before.update({str(path.relative_to(work)): path.read_bytes()
                           for path in (work / "frontend" / "settings").rglob("*") if path.is_file()})
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(work / "build_widget.ps1"),
                 "-ApiUrl", "https://api.example.test/api/v1"], cwd=work, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(work / "timesheet_il_widget.zip") as archive:
                self.assertEqual(set(archive.namelist()), RUNTIME)
                self.assertIn(b"https://api.example.test/api/v1", archive.read("i18n/en.json"))
                self.assertFalse(archive.read("i18n/en.json").startswith(b"\xef\xbb\xbf"))
            for name, content in before.items():
                self.assertEqual((work / name).read_bytes(), content, name)
            self.assertFalse((work / "temp_widget_build").exists())
            self.assertTrue(WidgetValidator(work / "timesheet_il_widget.zip").validate())


if __name__ == "__main__":
    unittest.main()
