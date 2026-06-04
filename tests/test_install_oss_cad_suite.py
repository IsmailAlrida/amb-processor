from __future__ import annotations

import unittest

from tools.install_oss_cad_suite import select_release_asset


class InstallOssCadSuiteTests(unittest.TestCase):
    def test_windows_release_asset_accepts_exe(self) -> None:
        payload = {
            "assets": [
                {
                    "name": "oss-cad-suite-windows-x64-20260418.exe",
                    "browser_download_url": "https://example.test/windows.exe",
                },
            ],
        }

        self.assertEqual(
            select_release_asset(payload, "2026-04-18", "windows-x64"),
            ("oss-cad-suite-windows-x64-20260418.exe", "https://example.test/windows.exe"),
        )

    def test_posix_release_asset_prefers_archive(self) -> None:
        payload = {
            "assets": [
                {
                    "name": "oss-cad-suite-linux-x64-20260418.exe",
                    "browser_download_url": "https://example.test/linux.exe",
                },
                {
                    "name": "oss-cad-suite-linux-x64-20260418.tgz",
                    "browser_download_url": "https://example.test/linux.tgz",
                },
            ],
        }

        self.assertEqual(
            select_release_asset(payload, "2026-04-18", "linux-x64"),
            ("oss-cad-suite-linux-x64-20260418.tgz", "https://example.test/linux.tgz"),
        )

    def test_missing_release_asset_fails_clearly(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            select_release_asset({"assets": []}, "2026-04-18", "windows-x64")

        self.assertIn("No OSS CAD Suite asset for windows-x64 in release 2026-04-18", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
