from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from tools.oss_cad_bundle import BundleOptions, collect_oss_cad_suite_bundle, collect_oss_cad_suite_datas


def write_file(root: Path, rel_path: str, content: str = "x") -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_bytes(root: Path, rel_path: str, content: bytes) -> None:
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def source_rels(entries: list[tuple[str, str]], root: Path) -> set[str]:
    root = root.resolve()
    rels: set[str] = set()
    for source, _dest in entries:
        try:
            rels.add(Path(source).resolve().relative_to(root).as_posix())
        except ValueError:
            continue
    return rels


class OssCadBundleTests(unittest.TestCase):
    def test_default_bundle_is_core_plus_surfer_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "oss-cad-suite"

            for tool in ("iverilog", "vvp", "vcd2fst", "surfer", "yosys", "dot", "gtkwave"):
                write_file(root, f"bin/{tool}")
                write_file(root, f"libexec/{tool}")

            for rel_path in (
                "VERSION",
                "README",
                "lib/ivl/vvp.conf",
                "lib/ivl/vvp.tgt",
                "lib/ivl/ivl",
                "lib/ivl/ivlpp",
                "lib/ivl/system.vpi",
                "libexec/realpath",
                "libexec/ivl",
                "libexec/ivlpp",
                "lib/libunused.so",
                "lib/python3.11/site.py",
                "lib/python2.7/site.py",
                "lib/yosys/cells.lib",
                "share/yosys/cells.lib",
                "lib/graphviz/config6",
                "share/graphviz/lefty.psp",
                "share/gtkwave/gtkwave.tcl",
            ):
                write_file(root, rel_path)

            report_path = Path(tmpdir) / "report.json"
            with redirect_stdout(StringIO()):
                entries = collect_oss_cad_suite_datas(
                    root,
                    "tools/oss-cad-suite/linux-x64/oss-cad-suite",
                    options=BundleOptions(platform_name="linux-x64"),
                    report_path=report_path,
                )
            rels = source_rels(entries, root)

            self.assertIn("bin/iverilog", rels)
            self.assertIn("bin/vvp", rels)
            self.assertIn("bin/vcd2fst", rels)
            self.assertIn("bin/surfer", rels)
            self.assertIn("lib/ivl/vvp.conf", rels)
            self.assertIn("libexec/realpath", rels)
            self.assertIn("libexec/ivl", rels)
            self.assertIn("libexec/ivlpp", rels)

            self.assertNotIn("bin/yosys", rels)
            self.assertNotIn("bin/dot", rels)
            self.assertNotIn("bin/gtkwave", rels)
            self.assertNotIn("lib/libunused.so", rels)
            self.assertNotIn("lib/python3.11/site.py", rels)
            self.assertNotIn("lib/python2.7/site.py", rels)
            self.assertNotIn("lib/yosys/cells.lib", rels)
            self.assertNotIn("share/yosys/cells.lib", rels)
            self.assertNotIn("lib/graphviz/config6", rels)
            self.assertNotIn("share/graphviz/lefty.psp", rels)
            self.assertNotIn("share/gtkwave/gtkwave.tcl", rels)
            self.assertTrue(report_path.exists())

    def test_darwin_mach_o_payloads_are_binaries_but_wrappers_stay_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "oss-cad-suite"

            for tool in ("iverilog", "vvp", "vcd2fst", "surfer"):
                write_file(root, f"bin/{tool}", "#!/usr/bin/env bash\n")
                write_bytes(root, f"libexec/{tool}", b"\xcf\xfa\xed\xfe" + b"payload")
            write_bytes(root, "libexec/realpath", b"\xcf\xfa\xed\xfe" + b"payload")

            for rel_path in (
                "VERSION",
                "README",
                "lib/ivl/vvp.conf",
                "lib/ivl/vvp.tgt",
                "libexec/ivl",
                "libexec/ivlpp",
            ):
                write_file(root, rel_path)
            write_bytes(root, "lib/ivl/system.vpi", b"\xfe\xed\xfa\xcf" + b"payload")

            bundle = collect_oss_cad_suite_bundle(
                root,
                "tools/oss-cad-suite/darwin-arm64/oss-cad-suite",
                options=BundleOptions(platform_name="darwin-arm64"),
            )
            data_rels = source_rels(bundle.datas, root)
            binary_rels = source_rels(bundle.binaries, root)

            self.assertIn("bin/iverilog", data_rels)
            self.assertIn("bin/vvp", data_rels)
            self.assertIn("bin/vcd2fst", data_rels)
            self.assertIn("bin/surfer", data_rels)
            self.assertIn("libexec/iverilog", binary_rels)
            self.assertIn("libexec/vvp", binary_rels)
            self.assertIn("libexec/vcd2fst", binary_rels)
            self.assertIn("libexec/surfer", binary_rels)
            self.assertIn("libexec/realpath", binary_rels)
            self.assertIn("lib/ivl/system.vpi", binary_rels)


if __name__ == "__main__":
    unittest.main()
