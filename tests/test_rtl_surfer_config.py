from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rtl.testbench import run_rtl_sim


class RtlSurferConfigTests(unittest.TestCase):
    def test_surfer_config_hides_parameters_and_uses_tree_hierarchy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            config_path = run_rtl_sim.write_surfer_config(out_dir)

            self.assertEqual(config_path.relative_to(out_dir).as_posix(), ".surfer/config.toml")
            self.assertFalse((out_dir / "cpu_trace.sucl").exists())

            config = config_path.read_text(encoding="utf-8")
            self.assertIn("[layout]", config)
            self.assertIn('hierarchy_style = "Tree"', config)
            self.assertIn('parameter_display_location = "None"', config)
            self.assertIn("show_empty_scopes = false", config)

    def test_surfer_launch_uses_waveform_directory_for_config_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            wave_path = out_dir / "cpu_tb.fst"

            with patch.object(run_rtl_sim.subprocess, "Popen") as popen:
                run_rtl_sim.popen_tool("surfer", [str(wave_path)], Path("/ignored"), None)

            self.assertEqual(popen.call_args.kwargs["cwd"], out_dir.resolve())


if __name__ == "__main__":
    unittest.main()
