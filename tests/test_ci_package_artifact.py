from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import ci_package_artifact


class CiPackageArtifactTests(unittest.TestCase):
    def test_macos_package_builds_drag_install_dmg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            app = repo_root / "dist" / "amb-assembler.app"
            app.mkdir(parents=True)
            output_dir = repo_root / "dist" / "artifacts"
            output_dir.mkdir(parents=True)

            def which(name: str) -> str | None:
                if name in {"ditto", "hdiutil"}:
                    return f"/usr/bin/{name}"
                return None

            with (
                mock.patch.object(ci_package_artifact, "REPO_ROOT", repo_root),
                mock.patch.object(ci_package_artifact.shutil, "which", side_effect=which),
                mock.patch.object(ci_package_artifact.subprocess, "run") as run,
            ):
                artifact = ci_package_artifact.package_macos("darwin-arm64", "0.1.1", output_dir)

            self.assertEqual(output_dir / "amb-assembler-darwin-arm64-0.1.1.dmg", artifact)
            self.assertEqual(2, run.call_count)
            ditto_cmd = run.call_args_list[0].args[0]
            hdiutil_cmd = run.call_args_list[1].args[0]

            self.assertEqual("/usr/bin/ditto", ditto_cmd[0])
            self.assertEqual(str(app), ditto_cmd[1])
            self.assertTrue(ditto_cmd[2].endswith("dmg-root/amb-assembler.app"))

            self.assertEqual(
                [
                    "/usr/bin/hdiutil",
                    "create",
                    "-volname",
                    "AMB Assembler",
                    "-srcfolder",
                ],
                hdiutil_cmd[:5],
            )
            self.assertTrue(hdiutil_cmd[5].endswith("dmg-root"))
            self.assertEqual(["-ov", "-format", "UDZO", str(artifact)], hdiutil_cmd[6:])


if __name__ == "__main__":
    unittest.main()
