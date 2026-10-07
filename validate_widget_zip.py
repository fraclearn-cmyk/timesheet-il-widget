#!/usr/bin/env python3
"""Validate the exact, credential-free runtime contents of an amoCRM widget ZIP."""

import json
import re
import sys
import zipfile
from pathlib import Path


RUNTIME_FILES = frozenset(
    {
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
)
TEXT_SUFFIXES = (".json", ".js", ".css", ".html")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}", re.IGNORECASE),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{16,}\.eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\b"),
)
SENSITIVE_KEY = (
    r"(?:amocrm[_-]?)?(?:client[_-]?secret|access[_-]?token|refresh[_-]?token)"
)
SENSITIVE_ASSIGNMENT = re.compile(
    rf"(?<![\w$])(?:[\"']{SENSITIVE_KEY}[\"']|{SENSITIVE_KEY})\s*[:=]\s*([\"'`])",
    re.IGNORECASE,
)


def has_named_secret_literal(content):
    """Flag nonempty string literals assigned to well-known credential names."""
    for match in SENSITIVE_ASSIGNMENT.finditer(content):
        quote = match.group(1)
        start = match.end()
        index = start
        while index < len(content):
            if content[index] == "\\":
                index += 2
            elif content[index] == quote:
                if content[start:index].strip():
                    return True
                break
            else:
                index += 1
    return False


def amd_dependencies(content):
    """Read literal AMD dependencies while ignoring comments inside the array."""
    opener = re.match(r"\s*define\s*\(\s*\[", content)
    if not opener:
        return []
    index = opener.end()
    dependencies = []
    while index < len(content):
        char = content[index]
        if char.isspace() or char == ",":
            index += 1
        elif char == "]":
            return dependencies
        elif content.startswith("//", index):
            end = content.find("\n", index + 2)
            index = len(content) if end < 0 else end + 1
        elif content.startswith("/*", index):
            end = content.find("*/", index + 2)
            if end < 0:
                return []
            index = end + 2
        elif char in ("'", '"'):
            quote = char
            start = index + 1
            index = start
            while index < len(content):
                if content[index] == "\\":
                    index += 2
                elif content[index] == quote:
                    dependencies.append(content[start:index])
                    index += 1
                    break
                else:
                    index += 1
            else:
                return []
        else:
            return []
    return []


class WidgetValidator:
    def __init__(self, zip_path):
        self.zip_path = Path(zip_path)
        self.errors = []

    def validate(self):
        self.errors = []
        try:
            with zipfile.ZipFile(self.zip_path) as archive:
                members = archive.infolist()
                names = [member.filename for member in members]
                missing = RUNTIME_FILES - set(names)
                extra = set(names) - RUNTIME_FILES
                self.errors.extend(
                    f"Missing runtime file: {name}" for name in sorted(missing)
                )
                self.errors.extend(f"Unexpected file: {name}" for name in sorted(extra))
                if len(names) != len(set(names)):
                    self.errors.append("Duplicate ZIP member name")
                if any(member.is_dir() for member in members):
                    self.errors.append("ZIP directory entries are not allowed")
                if any(member.flag_bits & 0x1 for member in members):
                    self.errors.append("Encrypted ZIP entries are not allowed")

                text = {}
                for name in sorted(set(names) & RUNTIME_FILES):
                    if name.endswith(".png"):
                        if not archive.read(name).startswith(b"\x89PNG\r\n\x1a\n"):
                            self.errors.append(f"Invalid PNG in {name}")
                        continue
                    if not name.endswith(TEXT_SUFFIXES):
                        continue
                    data = archive.read(name)
                    if data.startswith(b"\xef\xbb\xbf"):
                        self.errors.append(f"UTF-8 BOM in {name}")
                    try:
                        text[name] = data.decode("utf-8", errors="strict")
                    except UnicodeDecodeError:
                        self.errors.append(f"Invalid UTF-8 in {name}")
                for name, content in text.items():
                    if name.endswith(".json"):
                        try:
                            json.loads(content)
                        except json.JSONDecodeError:
                            self.errors.append(f"Invalid JSON in {name}")
                    if any(
                        pattern.search(content) for pattern in SECRET_PATTERNS
                    ) or has_named_secret_literal(content):
                        self.errors.append(f"Credential-like value in {name}")
                    if name.endswith(".js") and re.search(
                        r"typeof\s+define\s*===\s*['\"]function['\"]\s*&&\s*define\.amd",
                        content,
                    ):
                        self.errors.append(
                            f"{name} must register with the amoCRM define loader"
                        )

                if "manifest.json" in text:
                    try:
                        manifest = json.loads(text["manifest.json"])
                    except json.JSONDecodeError:
                        manifest = {}
                    if manifest.get("locations") != [
                        "settings",
                        "advanced_settings",
                        "everywhere",
                    ]:
                        self.errors.append(
                            "manifest.json locations must use settings, advanced_settings and everywhere for the floating widget UI"
                        )
                    if not isinstance(manifest.get("advanced"), dict) or not manifest[
                        "advanced"
                    ].get("title"):
                        self.errors.append("manifest.json advanced.title is required")
                if "script.js" in text and not re.search(
                    r"advancedSettings\s*:\s*function", text["script.js"]
                ):
                    self.errors.append(
                        "script.js must define advancedSettings callback"
                    )
                if "script.js" in text:
                    if not re.search(
                        r"return\s+this\s*;\s*};\s*return\s+CustomWidget\s*;",
                        text["script.js"],
                    ):
                        self.errors.append(
                            "script.js widget constructor must return this"
                        )
                    dependencies = amd_dependencies(text["script.js"])
                    if "./reports/controller" not in dependencies:
                        self.errors.append(
                            "Missing AMD dependency: reports/controller.js"
                        )
                    for dependency, member in (
                        ("./settings/settings", "settings/settings.js"),
                        ("./timesheet/controller", "timesheet/controller.js"),
                        ("./activity-tracker", "activity-tracker.js"),
                        ("./overlay", "overlay.js"),
                        ("./monitoring/timeline", "monitoring/timeline.js"),
                        ("./monitoring/activity-modal", "monitoring/activity-modal.js"),
                        ("./monitoring/dashboard", "monitoring/dashboard.js"),
                        ("./reports/controller", "reports/controller.js"),
                    ):
                        if dependency in text["script.js"] and member not in names:
                            self.errors.append(f"Missing AMD dependency: {member}")
                if (
                    "settings/settings.js" in text
                    and "SettingsController" not in text["settings/settings.js"]
                ):
                    self.errors.append("settings/settings.js is not the runtime editor")
        except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as exc:
            self.errors.append(f"Cannot inspect ZIP: {type(exc).__name__}")
        for error in self.errors:
            print(f"FAIL: {error}")
        if self.errors:
            print(f"VALIDATION FAILED: {len(self.errors)} error(s)")
            return False
        print(f"VALIDATION PASSED: {len(RUNTIME_FILES)} exact runtime files")
        return True


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Usage: python validate_widget_zip.py <widget.zip>")
        return 2
    return 0 if WidgetValidator(arguments[0]).validate() else 1


if __name__ == "__main__":
    sys.exit(main())
