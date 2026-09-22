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
    "manifest.json", "script.js", "overlay.js", "timesheet/controller.js", "styles.css",
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

    def test_validator_rejects_explicit_named_credential_literals(self):
        synthetic_assignments = [
            'const AMOCRM_CLIENT_SECRET = "synthetic-example-client-secret-value";',
            'const AMOCRM_ACCESS_TOKEN = "synthetic-example-access-token-value";',
            'const AMOCRM_REFRESH_TOKEN = "synthetic-example-refresh-token-value";',
            'const amoCrmAccessToken = "synthetic-example-access-token-value";',
            'const amoCrmRefreshToken = "synthetic-example-refresh-token-value";',
            "const clientSecret = 'synthetic-example-client-secret-value';",
            "const access_token = 'synthetic-example-access-token-value';",
            "const refreshToken = `synthetic-example-refresh-token-value`;",
            'const config = { "client_secret": "synthetic-example-client-secret-value" };',
        ]
        for assignment in synthetic_assignments:
            with self.subTest(assignment=assignment.split("=")[0]):
                entries = self.entries()
                entries["settings/settings.js"] += ("\n" + assignment).encode("utf-8")
                validator = WidgetValidator(self.make_zip(entries))
                self.assertFalse(validator.validate())
                self.assertIn("Credential-like value in settings/settings.js", validator.errors)

    def test_validator_allows_empty_credential_placeholders_and_identifier_references(self):
        entries = self.entries()
        entries["settings/settings.js"] += (
            '\nconst AMOCRM_CLIENT_SECRET = "";\n'
            'const AMOCRM_ACCESS_TOKEN = "";\n'
            "const AMOCRM_REFRESH_TOKEN = '';\n"
            "const access_token = '';\n"
            'const refreshToken = process.env.REFRESH_TOKEN;\n'
            'const amoCrmAccessToken = process.env.ACCESS_TOKEN;\n'
            'const config = { client_secret: AMOCRM_CLIENT_SECRET };\n'
        ).encode("utf-8")
        self.assertTrue(WidgetValidator(self.make_zip(entries)).validate())

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
            shutil.copy2(ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py")
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
            with zipfile.ZipFile(work / "widget.zip") as archive:
                self.assertEqual(set(archive.namelist()), RUNTIME)
                self.assertIn(b"https://example.com/api/v1", archive.read("i18n/en.json"))
                self.assertNotIn(b"https://api.example.test/api/v1", archive.read("i18n/en.json"))
                self.assertFalse(archive.read("i18n/en.json").startswith(b"\xef\xbb\xbf"))
            for name, content in before.items():
                self.assertEqual((work / name).read_bytes(), content, name)
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertEqual(list(work.glob(".widget-backup-*.zip")), [])
            self.assertTrue(WidgetValidator(work / "widget.zip").validate())

    def test_builder_replaces_an_existing_valid_archive_after_staged_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(ROOT / "frontend" / "settings", work / "frontend" / "settings")
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py")
            command = [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(work / "build_widget.ps1"), "-ApiUrl",
            ]
            first = subprocess.run(command + ["https://first.example.test/api/v1"], cwd=work,
                                   capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            previous_bytes = (work / "widget.zip").read_bytes()
            second = subprocess.run(command + ["https://second.example.test/api/v1"], cwd=work,
                                    capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            with zipfile.ZipFile(work / "widget.zip") as archive:
                self.assertIn(b"https://example.com/api/v1", archive.read("i18n/en.json"))
                self.assertNotIn(b"https://second.example.test/api/v1", archive.read("i18n/en.json"))
            self.assertNotEqual((work / "widget.zip").read_bytes(), previous_bytes)
            self.assertTrue(WidgetValidator(work / "widget.zip").validate())
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertEqual(list(work.glob(".widget-backup-*.zip")), [])

    def test_builder_removes_temporary_artifacts_after_missing_source_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(ROOT / "frontend" / "settings", work / "frontend" / "settings")
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py")
            (work / "frontend" / "settings" / "settings.css").unlink()
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(work / "build_widget.ps1"),
                 "-ApiUrl", "https://api.example.test/api/v1"], cwd=work, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing runtime source: settings/settings.css", result.stdout + result.stderr)
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertFalse((work / "widget.zip").exists())

    def test_builder_removes_temporary_artifacts_after_late_json_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(ROOT / "frontend" / "settings", work / "frontend" / "settings")
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py")
            (work / "widget" / "i18n" / "en.json").write_text("{ invalid", encoding="utf-8")
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(work / "build_widget.ps1"),
                 "-ApiUrl", "https://api.example.test/api/v1"], cwd=work, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid JSON in staged archive: i18n/en.json", result.stdout + result.stderr)
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertFalse((work / "widget.zip").exists())

    def test_builder_does_not_publish_zip_with_synthetic_named_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(ROOT / "frontend" / "settings", work / "frontend" / "settings")
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py")
            settings = work / "frontend" / "settings" / "settings.js"
            settings.write_bytes(settings.read_bytes() +
                b'\nconst AMOCRM_ACCESS_TOKEN = "synthetic-example-access-token-value";\n')
            previous_archive = work / "widget.zip"
            previous_archive.write_bytes(b"previous validated archive")
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(work / "build_widget.ps1"),
                 "-ApiUrl", "https://api.example.test/api/v1"], cwd=work, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Staged widget ZIP failed validation", result.stdout + result.stderr)
            self.assertNotIn("synthetic-example-access-token-value", result.stdout + result.stderr)
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertEqual(previous_archive.read_bytes(), b"previous validated archive")


if __name__ == "__main__":
    unittest.main()
