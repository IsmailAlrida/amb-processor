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


if __name__ == "__main__":
    unittest.main()
