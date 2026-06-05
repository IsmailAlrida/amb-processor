from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ci_package_artifact


class CiPackageArtifactTests(unittest.TestCase):
    def test_macos_package_uses_ditto(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            app = repo_root / "dist" / "amb-assembler.app"
            app.mkdir(parents=True)
            output_dir = repo_root / "dist" / "artifacts"
            output_dir.mkdir(parents=True)

            with (
                mock.patch.object(ci_package_artifact, "REPO_ROOT", repo_root),
                mock.patch.object(ci_package_artifact.shutil, "which", return_value="/usr/bin/ditto"),
                mock.patch.object(ci_package_artifact.subprocess, "run") as run,
            ):
                artifact = ci_package_artifact.package_macos("darwin-arm64", "0.1.1", output_dir)

            self.assertEqual(output_dir / "amb-assembler-darwin-arm64-0.1.1.zip", artifact)
            run.assert_called_once_with(
                [
                    "/usr/bin/ditto",
                    "-c",
                    "-k",
                    "--sequesterRsrc",
                    "--keepParent",
                    str(app),
                    str(artifact),
                ],
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
