#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Path Translation Module for Server Deployment

Translates Windows network paths (e.g., \\server\share\folder) to local
Linux mount points (e.g., /mnt/shares/share-name/folder).

Configuration is loaded from /etc/asset-converter/path-mapping.conf
"""

from pathlib import Path, PureWindowsPath
import re
from typing import Optional


class PathTranslator:
    """Translates Windows UNC paths and mapped drives to Linux mount points."""

    def __init__(self, config_path: str = "/etc/asset-converter/path-mapping.conf"):
        self.config_path = config_path
        self.mappings = {}  # UNC path mappings
        self.drive_mappings = {}  # Drive letter mappings
        self.load_mappings()

    def load_mappings(self):
        """Load path mappings from configuration file.

        Supports two formats:
        1. UNC paths: //server/share|/local/mount/point
        2. Drive letters: T:|//server/share|/local/mount/point
        """
        try:
            config_file = Path(self.config_path)
            if not config_file.exists():
                print(f"Warning: Config file not found: {self.config_path}")
                print("Running in local mode (no path translation)")
                return

            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    # Parse mapping
                    if '|' in line:
                        parts = line.split('|')

                        # Check if this is a drive letter mapping (3 parts) or UNC mapping (2 parts)
                        if len(parts) == 3:
                            # Format: T:|//server/share|/local/mount/point
                            drive_letter = parts[0].strip().upper().rstrip(':')
                            smb_path = parts[1].strip()
                            local_path = parts[2].strip()

                            # Normalize SMB path
                            smb_path = smb_path.replace('\\', '/')
                            if not smb_path.startswith('//'):
                                smb_path = '//' + smb_path

                            # Store both mappings
                            self.drive_mappings[drive_letter] = local_path
                            self.mappings[smb_path.lower()] = local_path
                            print(f"Loaded drive mapping: {drive_letter}: -> {local_path} (via {smb_path})")

                        elif len(parts) == 2:
                            # Format: //server/share|/local/mount/point
                            smb_path = parts[0].strip()
                            local_path = parts[1].strip()

                            # Normalize SMB path (handle both // and \\)
                            smb_path = smb_path.replace('\\', '/')
                            if not smb_path.startswith('//'):
                                smb_path = '//' + smb_path

                            # Store mapping (case-insensitive for Windows paths)
                            self.mappings[smb_path.lower()] = local_path
                            print(f"Loaded UNC mapping: {smb_path} -> {local_path}")

        except Exception as e:
            print(f"Error loading path mappings: {e}")

    def translate_path(self, path: str) -> str:
        """
        Translate a Windows path to Linux path.

        Supports:
        - Mapped drives: T:\\folder\\file -> /mnt/shares/share/folder/file
        - UNC paths: \\\\server\\share\\folder -> /mnt/shares/share/folder
        - Forward slash UNC: //server/share/folder
        - Local paths: C:\\local\\path (returns as-is for local server paths)

        Args:
            path: Windows path string

        Returns:
            Translated Linux path or original path if no mapping found
        """
        if not path or not path.strip():
            return path

        original_path = path
        path = path.strip()

        # If no mappings configured, return as-is (local mode)
        if not self.mappings and not self.drive_mappings:
            return path

        # Normalize Windows path separators
        normalized_path = path.replace('\\', '/')

        # Check for mapped drive letter (e.g., T:/folder/file)
        drive_match = re.match(r'^([A-Za-z]):(/|$)(.*)', normalized_path)
        if drive_match:
            drive_letter = drive_match.group(1).upper()
            remaining = drive_match.group(3)

            if drive_letter in self.drive_mappings:
                mount_point = self.drive_mappings[drive_letter]
                if remaining:
                    translated = f"{mount_point}/{remaining}"
                else:
                    translated = mount_point

                print(f"Path translation (drive): {original_path} -> {translated}")
                return translated
            else:
                print(f"Warning: No mapping found for drive {drive_letter}:")
                print(f"Available drive mappings: {list(self.drive_mappings.keys())}")
                return original_path

        # Check if this looks like a UNC path
        if normalized_path.startswith('//') or original_path.startswith('\\\\'):
            # Ensure it starts with //
            if not normalized_path.startswith('//'):
                normalized_path = '//' + normalized_path.lstrip('/')

            # Extract the server and share portion
            # Format: //server/share/remaining/path
            parts = normalized_path[2:].split('/', 2)  # Skip leading //

            if len(parts) >= 2:
                server = parts[0]
                share = parts[1]
                remaining = parts[2] if len(parts) > 2 else ""

                # Try to find a matching mapping (case-insensitive)
                unc_prefix = f"//{server}/{share}".lower()

                if unc_prefix in self.mappings:
                    mount_point = self.mappings[unc_prefix]
                    if remaining:
                        translated = f"{mount_point}/{remaining}"
                    else:
                        translated = mount_point

                    print(f"Path translation (UNC): {original_path} -> {translated}")
                    return translated
                else:
                    print(f"Warning: No mapping found for {unc_prefix}")
                    print(f"Available UNC mappings: {list(self.mappings.keys())}")

        # If no translation found, return original path
        return original_path

    def get_all_mappings(self) -> dict:
        """Return all configured UNC path mappings."""
        return self.mappings.copy()

    def get_drive_mappings(self) -> dict:
        """Return all configured drive letter mappings."""
        return self.drive_mappings.copy()


# Singleton instance
_translator = None


def get_translator() -> PathTranslator:
    """Get or create the global PathTranslator instance."""
    global _translator
    if _translator is None:
        _translator = PathTranslator()
    return _translator


def translate_path(path: str) -> str:
    """
    Convenience function to translate a path using the global translator.

    Args:
        path: Windows path string

    Returns:
        Translated Linux path or original path if no mapping found
    """
    translator = get_translator()
    return translator.translate_path(path)


# Test function
if __name__ == "__main__":
    import sys

    translator = PathTranslator()

    print("\nConfigured UNC mappings:")
    for smb, local in translator.get_all_mappings().items():
        print(f"  {smb} -> {local}")

    print("\nConfigured drive mappings:")
    for drive, local in translator.get_drive_mappings().items():
        print(f"  {drive}: -> {local}")

    print("\nTest translations:")
    test_paths = [
        "T:\\00005 Büroportfolio\\00_Projekte\\02735 WKB - Kita Beuren",
        "\\\\fileserver\\projects\\client-abc\\images",
        "//fileserver/projects/client-abc/images",
        "\\\\nas\\media\\photos",
        "P:\\shared\\documents",
        "/local/path/on/server",
        "C:\\Windows\\Path",
    ]

    for test_path in test_paths:
        translated = translator.translate_path(test_path)
        print(f"  {test_path}")
        print(f"    -> {translated}")
        print()
