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
    """Translates Windows UNC paths to Linux mount points."""

    def __init__(self, config_path: str = "/etc/asset-converter/path-mapping.conf"):
        self.config_path = config_path
        self.mappings = {}
        self.load_mappings()

    def load_mappings(self):
        """Load path mappings from configuration file."""
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

                    # Parse mapping: //server/share|/local/mount/point
                    if '|' in line:
                        smb_path, local_path = line.split('|', 1)
                        smb_path = smb_path.strip()
                        local_path = local_path.strip()

                        # Normalize SMB path (handle both // and \\)
                        smb_path = smb_path.replace('\\', '/')
                        if not smb_path.startswith('//'):
                            smb_path = '//' + smb_path

                        # Store mapping (case-insensitive for Windows paths)
                        self.mappings[smb_path.lower()] = local_path
                        print(f"Loaded mapping: {smb_path} -> {local_path}")

        except Exception as e:
            print(f"Error loading path mappings: {e}")

    def translate_path(self, path: str) -> str:
        """
        Translate a Windows path to Linux path.

        Supports:
        - UNC paths: \\server\share\folder -> /mnt/shares/share/folder
        - Forward slash UNC: //server/share/folder
        - Mixed: C:\local\path (returns as-is for local server paths)

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
        if not self.mappings:
            return path

        # Normalize Windows path separators
        path = path.replace('\\', '/')

        # Check if this looks like a UNC path
        if path.startswith('//') or original_path.startswith('\\\\'):
            # Ensure it starts with //
            if not path.startswith('//'):
                path = '//' + path.lstrip('/')

            # Extract the server and share portion
            # Format: //server/share/remaining/path
            parts = path[2:].split('/', 2)  # Skip leading //

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

                    print(f"Path translation: {original_path} -> {translated}")
                    return translated
                else:
                    print(f"Warning: No mapping found for {unc_prefix}")
                    print(f"Available mappings: {list(self.mappings.keys())}")

        # If no translation found, return original path
        return original_path

    def get_all_mappings(self) -> dict:
        """Return all configured path mappings."""
        return self.mappings.copy()


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

    print("\nConfigured mappings:")
    for smb, local in translator.get_all_mappings().items():
        print(f"  {smb} -> {local}")

    print("\nTest translations:")
    test_paths = [
        "\\\\fileserver\\projects\\client-abc\\images",
        "//fileserver/projects/client-abc/images",
        "\\\\nas\\media\\photos",
        "/local/path/on/server",
        "C:\\Windows\\Path",
    ]

    for test_path in test_paths:
        translated = translator.translate_path(test_path)
        print(f"  {test_path}")
        print(f"    -> {translated}")
        print()
