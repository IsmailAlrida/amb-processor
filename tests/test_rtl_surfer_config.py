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

            config = config_path.read_text(encoding="utf-8")
            self.assertIn('autoload_sibling_state_files = "Never"', config)
            self.assertIn("[layout]", config)
            self.assertIn('hierarchy_style = "Tree"', config)
            self.assertIn('parameter_display_location = "None"', config)
            self.assertIn("show_empty_scopes = false", config)

    def test_surfer_command_file_forces_tree_after_waveform_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            command_path = run_rtl_sim.write_surfer_command_file(out_dir)

            self.assertEqual(command_path.relative_to(out_dir).as_posix(), "cpu_trace.sucl")
            self.assertEqual(
                command_path.read_text(encoding="utf-8"),
                "preference_set_hierarchy_style Tree\n",
            )

    def test_surfer_launch_uses_waveform_directory_for_config_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            wave_path = out_dir / "cpu_tb.fst"

            with patch.object(run_rtl_sim.subprocess, "Popen") as popen:
                run_rtl_sim.popen_tool("surfer", [str(wave_path)], Path("/ignored"), None)

            cmd = popen.call_args.args[0]
            command_path = out_dir / "cpu_trace.sucl"
            self.assertEqual(popen.call_args.kwargs["cwd"], out_dir.resolve())
            self.assertEqual(
                cmd,
                [
                    "surfer",
                    "--command-file",
                    str(command_path.resolve()),
                    str(wave_path.resolve()),
                ],
            )
            self.assertTrue((out_dir / ".surfer" / "config.toml").exists())
            self.assertTrue(command_path.exists())

    def test_darwin_bundled_tools_use_libexec_and_quote_space_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            oss_root = (
                Path(tmpdir)
                / "amb-assembler 2.app"
                / "Contents"
                / "Resources"
                / "tools"
                / "oss-cad-suite"
                / "darwin-arm64"
                / "oss-cad-suite"
            )
            for rel_path in (
                "bin/iverilog",
                "bin/vvp",
                "libexec/iverilog",
                "libexec/vvp",
                "libexec/vcd2fst",
                "libexec/surfer",
                "lib/libexample.dylib",
            ):
                path = oss_root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            with patch.object(run_rtl_sim.platform, "system", return_value="Darwin"):
                iverilog = run_rtl_sim.tool_path("iverilog", oss_root)
                env = run_rtl_sim.tool_environment(oss_root)
                cmd, use_shell = run_rtl_sim.command_for_tool(iverilog, ["-g2012"], oss_root)

            self.assertEqual(str(oss_root / "libexec" / "iverilog"), iverilog)
            self.assertFalse(use_shell)
            self.assertEqual(
                [
                    str(oss_root / "libexec" / "iverilog"),
                    "-p",
                    f"VVP_EXECUTABLE={oss_root / 'libexec' / 'vvp'}",
                    "-g2012",
                ],
                cmd,
            )
            self.assertIsNotNone(env)
            assert env is not None
            self.assertEqual(str(oss_root), env["YOSYSHQ_ROOT"])
            self.assertTrue(env["PATH"].startswith(str(oss_root / "bin")))
            self.assertIn(str(oss_root / "libexec"), env["PATH"])
            self.assertIn(str(oss_root / "lib"), env["DYLD_LIBRARY_PATH"])
            printable = run_rtl_sim._display_command(cmd)
            self.assertTrue(printable.startswith("'"))
            self.assertIn("amb-assembler 2.app", printable)

    def test_darwin_surfer_launch_uses_bundled_libexec_from_waveform_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            oss_root = root / "amb-assembler 2.app" / "Contents" / "Resources" / "tools" / "oss-cad-suite" / "darwin-arm64" / "oss-cad-suite"
            surfer = oss_root / "libexec" / "surfer"
            surfer.parent.mkdir(parents=True, exist_ok=True)
            surfer.write_text("", encoding="utf-8")
            for rel_path in ("bin", "lib"):
                (oss_root / rel_path).mkdir(parents=True, exist_ok=True)

            out_dir = root / "wave output"
            out_dir.mkdir()
            wave_path = out_dir / "cpu_tb.fst"

            with (
                patch.object(run_rtl_sim.platform, "system", return_value="Darwin"),
                patch.object(run_rtl_sim.subprocess, "Popen") as popen,
            ):
                run_rtl_sim.popen_tool(str(surfer), [str(wave_path)], Path("/ignored"), oss_root)

            cmd = popen.call_args.args[0]
            command_path = out_dir / "cpu_trace.sucl"
            self.assertEqual(out_dir.resolve(), popen.call_args.kwargs["cwd"])
            self.assertEqual(
                [
                    str(surfer),
                    "--command-file",
                    str(command_path.resolve()),
                    str(wave_path.resolve()),
                ],
                cmd,
            )
            self.assertFalse(popen.call_args.kwargs["shell"])
            self.assertEqual(str(oss_root), popen.call_args.kwargs["env"]["YOSYSHQ_ROOT"])


if __name__ == "__main__":
    unittest.main()
