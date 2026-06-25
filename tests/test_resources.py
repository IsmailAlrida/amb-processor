from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from assembler import resources


class ResourcePathTests(unittest.TestCase):
    def test_frozen_darwin_prefers_contents_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            contents = Path(tmpdir) / "amb-assembler.app" / "Contents"
            frameworks = contents / "Frameworks"
            resources_root = contents / "Resources"
            frameworks.mkdir(parents=True)
            resources_root.mkdir()

            with (
                mock.patch.object(sys, "frozen", True, create=True),
                mock.patch.object(sys, "_MEIPASS", str(frameworks), create=True),
                mock.patch.object(resources.platform, "system", return_value="Darwin"),
            ):
                self.assertEqual(resources_root.resolve(), resources.app_root())

    def test_source_build_prefers_env_oss_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_root = Path(tmpdir) / "repo"
            env_root = Path(tmpdir) / "external" / "oss-cad-suite"
            bundled_root = base_root / "tools" / "oss-cad-suite" / "darwin-arm64" / "oss-cad-suite"
            env_root.mkdir(parents=True)
            bundled_root.mkdir(parents=True)

            with (
                mock.patch.dict(resources.os.environ, {resources.OSS_CAD_SUITE_ENV_VAR: str(env_root)}),
                mock.patch.object(sys, "frozen", False, create=True),
                mock.patch.object(resources.platform, "system", return_value="Darwin"),
            ):
                self.assertEqual(
                    env_root.resolve(),
                    resources.resolve_oss_root(base_root, "darwin-arm64"),
                )

    def test_frozen_darwin_prefers_bundled_oss_root_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_root = Path(tmpdir) / "amb-assembler.app" / "Contents" / "Resources"
            env_root = Path(tmpdir) / "external" / "oss-cad-suite"
            bundled_root = base_root / "tools" / "oss-cad-suite" / "darwin-arm64" / "oss-cad-suite"
            env_root.mkdir(parents=True)
            bundled_root.mkdir(parents=True)

            with (
                mock.patch.dict(resources.os.environ, {resources.OSS_CAD_SUITE_ENV_VAR: str(env_root)}),
                mock.patch.object(sys, "frozen", True, create=True),
                mock.patch.object(resources.platform, "system", return_value="Darwin"),
            ):
                self.assertEqual(
                    bundled_root.resolve(),
                    resources.resolve_oss_root(base_root, "darwin-arm64"),
                )


if __name__ == "__main__":
    unittest.main()
