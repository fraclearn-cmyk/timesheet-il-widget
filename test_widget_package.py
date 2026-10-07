"""Contract tests for the installable amoCRM ZIP, without touching live amoCRM."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from validate_widget_zip import WidgetValidator


ROOT = Path(__file__).resolve().parent
BUILD_ENV = {
    **os.environ,
    "PATH": str(Path(sys.executable).resolve().parent)
    + os.pathsep
    + os.environ.get("PATH", ""),
}
RUNTIME = {
    "manifest.json",
    "script.js",
    "overlay.js",
    "activity-tracker.js",
    "timesheet/controller.js",
    "styles.css",
    "settings/settings.html",
    "settings/settings.js",
    "settings/settings.css",
    "monitoring/dashboard.js",
    "monitoring/activity-modal.js",
    "monitoring/timeline.js",
    "monitoring/styles.css",
    "reports/controller.js",
    "reports/styles.css",
    "i18n/ru.json",
    "i18n/en.json",
    "images/icon.png",
    "images/logo.png",
    "images/logo_main.png",
    "images/logo_medium.png",
    "images/logo_min.png",
    "images/logo_small.png",
    "images/tour_en.png",
    "images/tour_ru.png",
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
            source_root = (
                "frontend"
                if name.startswith(("settings/", "monitoring/", "reports/"))
                else "widget"
            )
            source = ROOT / source_root / name
            result[name] = source.read_bytes()
        return result

    def test_validator_rejects_missing_settings_asset(self):
        entries = self.entries()
        del entries["settings/settings.js"]
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(
            any("settings/settings.js" in error for error in validator.errors)
        )

    def test_manifest_uses_floating_ui_locations_without_card_sidebar(self):
        manifest = json.loads((ROOT / "widget" / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["widget"]["version"], "3.0.6")
        self.assertEqual(
            manifest["locations"],
            [
                "settings",
                "advanced_settings",
                "everywhere",
            ],
        )

    def test_validator_requires_widget_constructor_to_return_instance(self):
        entries = self.entries()
        entries["script.js"] = entries["script.js"].replace(
            b"        return this;\n    };\n    return CustomWidget;",
            b"    };\n    return CustomWidget;",
        )
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertIn(
            "script.js widget constructor must return this", validator.errors
        )

    def test_validator_rejects_modules_that_require_define_amd_marker(self):
        entries = self.entries()
        entries["overlay.js"] = entries["overlay.js"].replace(
            b"typeof define === 'function') define(factory)",
            b"typeof define === 'function' && define.amd) define(factory)",
        )
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertIn(
            "overlay.js must register with the amoCRM define loader",
            validator.errors,
        )

    def test_validator_requires_report_dependency_and_exact_report_assets(self):
        entries = self.entries()
        entries["script.js"] = (
            entries["script.js"].replace(
                b"'./reports/controller'", b"'./reports/missing'"
            )
            + b"\n// './reports/controller'\n"
        )
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(
            any("reports/controller" in error for error in validator.errors)
        )
        entries = self.entries()
        del entries["reports/styles.css"]
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertTrue(
            any("reports/styles.css" in error for error in validator.errors)
        )

    def test_validator_rejects_report_dependency_only_inside_amd_array_comment(self):
        entries = self.entries()
        entries["script.js"] = entries["script.js"].replace(
            b"'./reports/controller'",
            b"'./reports/missing', /* './reports/controller' */",
            1,
        )
        validator = WidgetValidator(self.make_zip(entries))
        self.assertFalse(validator.validate())
        self.assertIn("Missing AMD dependency: reports/controller.js", validator.errors)

    def test_validator_rejects_extra_secret_or_source_map(self):
        for name in [
            ".env",
            "settings/.env.production",
            "script.js.map",
            "frontend/admin.html",
        ]:
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
        entries[
            "settings/settings.html"
        ] += b"\nBearer abcdefghijklmnopqrstuvwxyz123456\n"
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
                self.assertIn(
                    "Credential-like value in settings/settings.js", validator.errors
                )

    def test_validator_allows_empty_credential_placeholders_and_identifier_references(
        self,
    ):
        entries = self.entries()
        entries["settings/settings.js"] += (
            '\nconst AMOCRM_CLIENT_SECRET = "";\n'
            'const AMOCRM_ACCESS_TOKEN = "";\n'
            "const AMOCRM_REFRESH_TOKEN = '';\n"
            "const access_token = '';\n"
            "const refreshToken = process.env.REFRESH_TOKEN;\n"
            "const amoCrmAccessToken = process.env.ACCESS_TOKEN;\n"
            "const config = { client_secret: AMOCRM_CLIENT_SECRET };\n"
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
            shutil.copytree(
                ROOT / "frontend" / "settings", work / "frontend" / "settings"
            )
            shutil.copytree(
                ROOT / "frontend" / "monitoring", work / "frontend" / "monitoring"
            )
            shutil.copytree(
                ROOT / "frontend" / "reports", work / "frontend" / "reports"
            )
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(
                ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py"
            )
            locale = work / "widget" / "i18n" / "en.json"
            locale.write_bytes(b"\xef\xbb\xbf" + locale.read_bytes())
            before = {
                str(path.relative_to(work)): path.read_bytes()
                for path in (work / "widget").rglob("*")
                if path.is_file()
            }
            before.update(
                {
                    str(path.relative_to(work)): path.read_bytes()
                    for path in (work / "frontend" / "settings").rglob("*")
                    if path.is_file()
                }
            )
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(work / "build_widget.ps1"),
                    "-ApiUrl",
                    "https://api.example.test/api/v1",
                ],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("-ApiUrl is deprecated", result.stdout + result.stderr)
            with zipfile.ZipFile(work / "widget.zip") as archive:
                self.assertEqual(set(archive.namelist()), RUNTIME)
                self.assertIn(
                    b"https://example.com/api/v1", archive.read("i18n/en.json")
                )
                self.assertNotIn(
                    b"https://api.example.test/api/v1", archive.read("i18n/en.json")
                )
                self.assertFalse(
                    archive.read("i18n/en.json").startswith(b"\xef\xbb\xbf")
                )
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
            shutil.copytree(
                ROOT / "frontend" / "settings", work / "frontend" / "settings"
            )
            shutil.copytree(
                ROOT / "frontend" / "monitoring", work / "frontend" / "monitoring"
            )
            shutil.copytree(
                ROOT / "frontend" / "reports", work / "frontend" / "reports"
            )
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(
                ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py"
            )
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(work / "build_widget.ps1"),
                "-ApiUrl",
            ]
            first = subprocess.run(
                command + ["https://first.example.test/api/v1"],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            replacement_script = (
                work / "widget" / "script.js"
            ).read_bytes() + b"\n// Replacement fixture revision.\n"
            (work / "widget" / "script.js").write_bytes(replacement_script)
            second = subprocess.run(
                command + ["https://second.example.test/api/v1"],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            with zipfile.ZipFile(work / "widget.zip") as archive:
                self.assertEqual(archive.read("script.js"), replacement_script)
                self.assertIn(
                    b"https://example.com/api/v1", archive.read("i18n/en.json")
                )
                self.assertNotIn(
                    b"https://second.example.test/api/v1", archive.read("i18n/en.json")
                )
            self.assertTrue(WidgetValidator(work / "widget.zip").validate())
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertEqual(list(work.glob(".widget-backup-*.zip")), [])

    def test_builder_removes_temporary_artifacts_after_missing_source_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(
                ROOT / "frontend" / "settings", work / "frontend" / "settings"
            )
            shutil.copytree(
                ROOT / "frontend" / "monitoring", work / "frontend" / "monitoring"
            )
            shutil.copytree(
                ROOT / "frontend" / "reports", work / "frontend" / "reports"
            )
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(
                ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py"
            )
            (work / "frontend" / "settings" / "settings.css").unlink()
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(work / "build_widget.ps1"),
                    "-ApiUrl",
                    "https://api.example.test/api/v1",
                ],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Missing runtime source: settings/settings.css",
                result.stdout + result.stderr,
            )
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertFalse((work / "widget.zip").exists())

    def test_builder_removes_temporary_artifacts_after_late_json_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(
                ROOT / "frontend" / "settings", work / "frontend" / "settings"
            )
            shutil.copytree(
                ROOT / "frontend" / "monitoring", work / "frontend" / "monitoring"
            )
            shutil.copytree(
                ROOT / "frontend" / "reports", work / "frontend" / "reports"
            )
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(
                ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py"
            )
            (work / "widget" / "i18n" / "en.json").write_text(
                "{ invalid", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(work / "build_widget.ps1"),
                    "-ApiUrl",
                    "https://api.example.test/api/v1",
                ],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Invalid JSON in staged archive: i18n/en.json",
                result.stdout + result.stderr,
            )
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertFalse((work / "widget.zip").exists())

    def test_builder_does_not_publish_zip_with_synthetic_named_secret(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / "widget", work / "widget")
            shutil.copytree(
                ROOT / "frontend" / "settings", work / "frontend" / "settings"
            )
            shutil.copytree(
                ROOT / "frontend" / "monitoring", work / "frontend" / "monitoring"
            )
            shutil.copytree(
                ROOT / "frontend" / "reports", work / "frontend" / "reports"
            )
            shutil.copy2(ROOT / "build_widget.ps1", work / "build_widget.ps1")
            shutil.copy2(
                ROOT / "validate_widget_zip.py", work / "validate_widget_zip.py"
            )
            settings = work / "frontend" / "settings" / "settings.js"
            settings.write_bytes(
                settings.read_bytes()
                + b'\nconst AMOCRM_ACCESS_TOKEN = "synthetic-example-access-token-value";\n'
            )
            previous_archive = work / "widget.zip"
            previous_archive.write_bytes(b"previous validated archive")
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(work / "build_widget.ps1"),
                    "-ApiUrl",
                    "https://api.example.test/api/v1",
                ],
                cwd=work,
                capture_output=True,
                text=True,
                env=BUILD_ENV,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Staged widget ZIP failed validation", result.stdout + result.stderr
            )
            self.assertNotIn(
                "synthetic-example-access-token-value", result.stdout + result.stderr
            )
            self.assertEqual(list(work.glob(".widget-stage-*")), [])
            self.assertEqual(list(work.glob(".widget-package-*.zip")), [])
            self.assertEqual(
                previous_archive.read_bytes(), b"previous validated archive"
            )


if __name__ == "__main__":
    unittest.main()
