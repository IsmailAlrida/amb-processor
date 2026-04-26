#!/usr/bin/env python3
"""Run the AMB RTL CPU testbench with OSS CAD Suite-compatible tools."""

from __future__ import annotations

import argparse
import html
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[3]


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "windows-x64"
    if system == "linux" and machine in {"x86_64", "amd64"}:
        return "linux-x64"
    return f"{system}-{machine}"


REPO_ROOT = app_root()
RTL_DIR = REPO_ROOT / "src" / "rtl"
TB_DIR = RTL_DIR / "testbench"
PROCESSOR_DIR = RTL_DIR / "processor"
DEFAULT_RUN_ROOT = (
    Path(os.environ.get("AMB_PROCESSOR_RUN_DIR", Path.home() / ".amb-processor")) / "rtl_sim"
    if getattr(sys, "frozen", False)
    else REPO_ROOT / "build" / "rtl_sim"
)

RTL_SOURCES = [
    TB_DIR / "tb.v",
    PROCESSOR_DIR / "cpu.v",
    PROCESSOR_DIR / "i_memory.v",
    PROCESSOR_DIR / "d_memory.v",
    PROCESSOR_DIR / "reg_file.v",
    PROCESSOR_DIR / "alu.v",
    PROCESSOR_DIR / "control_unit.v",
]

CPU_CORE_SOURCES = [
    PROCESSOR_DIR / "cpu.v",
    PROCESSOR_DIR / "reg_file.v",
    PROCESSOR_DIR / "alu.v",
    PROCESSOR_DIR / "control_unit.v",
]


def default_oss_root() -> Path | None:
    candidate = REPO_ROOT / "tools" / "oss-cad-suite" / platform_key() / "oss-cad-suite"
    return candidate if candidate.exists() else None


def tool_path(name: str, oss_root: Path | None) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    if oss_root is not None:
        candidate = oss_root / "bin" / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)
    return shutil.which(f"{name}{suffix}") or shutil.which(name) or name


def command_for_tool(tool: str, args: list[str], oss_root: Path | None) -> tuple[list[str] | str, bool]:
    if os.name != "nt" or oss_root is None:
        return [tool, *args], False
    env_bat = oss_root / "environment.bat"
    if not env_bat.exists():
        return [tool, *args], False
    cmdline = subprocess.list2cmdline([tool, *args])
    return f'call "{env_bat}" && {cmdline}', True


def run_tool(
    tool: str,
    args: list[str],
    cwd: Path,
    log_file: Path,
    oss_root: Path | None,
) -> subprocess.CompletedProcess[str]:
    cmd, use_shell = command_for_tool(tool, args, oss_root)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        shell=use_shell,
    )
    printable = cmd if isinstance(cmd, str) else " ".join(cmd)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("$ " + printable + "\n")
        handle.write(proc.stdout)
        if proc.stdout and not proc.stdout.endswith("\n"):
            handle.write("\n")
        handle.write(f"[exit {proc.returncode}]\n\n")
    return proc


def maybe_generate_schematic(oss_root: Path | None, out_dir: Path, log_file: Path, enabled: bool) -> None:
    if not enabled:
        return

    yosys = tool_path("yosys", oss_root)
    dot = tool_path("dot", oss_root)
    dot_path = out_dir / "cpu_schematic.dot"
    svg_path = out_dir / "cpu_schematic.svg"
    script = (
        "read_verilog -sv "
        + " ".join(str(path) for path in CPU_CORE_SOURCES)
        + f"; hierarchy -top cpu; proc; opt_clean; show -format dot -prefix {out_dir / 'cpu_schematic'} cpu"
    )
    proc = run_tool(yosys, ["-p", script], REPO_ROOT, log_file, oss_root)
    if proc.returncode != 0:
        return
    if dot_path.exists():
        run_tool(dot, ["-Tsvg", str(dot_path), "-o", str(svg_path)], REPO_ROOT, log_file, oss_root)


def write_html_index(out_dir: Path, result: dict[str, object], report_path: Path) -> Path:
    html_path = out_dir / "index.html"
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "{}\n"
    schematic_svg = out_dir / "cpu_schematic.svg"
    schematic_block = (
        '<section><h2>CPU Schematic</h2><img src="cpu_schematic.svg" alt="CPU schematic"></section>'
        if schematic_svg.exists()
        else "<section><h2>CPU Schematic</h2><p>Not generated for this run.</p></section>"
    )
    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AMB RTL Run: {html.escape(str(result["run_name"]))}</title>
  <style>
    body {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; margin: 2rem; background: #f7f4ed; color: #1f2933; }}
    header {{ display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; margin-bottom: 1.5rem; }}
    a {{ color: #0f5f6d; font-weight: 700; }}
    .pill {{ border: 1px solid #c8bfae; border-radius: 999px; padding: .35rem .75rem; background: #fffaf0; }}
    section {{ background: white; border: 1px solid #ddd3c3; border-radius: 12px; padding: 1rem; margin: 1rem 0; }}
    pre {{ overflow: auto; background: #15202b; color: #e6edf3; padding: 1rem; border-radius: 10px; }}
    img {{ max-width: 100%; background: white; }}
  </style>
</head>
<body>
  <header>
    <h1>AMB RTL Run</h1>
    <span class="pill">returncode={result["returncode"]}</span>
    <a href="result.json">result.json</a>
    <a href="summary.json">summary.json</a>
    <a href="run.log">run.log</a>
    <a href="cpu_tb.vcd">VCD</a>
    <a href="cpu_tb.fst">FST</a>
  </header>
  <section>
    <h2>Result</h2>
    <pre>{html.escape(report_text)}</pre>
  </section>
  {schematic_block}
</body>
</html>
""",
        encoding="utf-8",
    )
    return html_path


def run_simulation(
    *,
    run_name: str = "array_sum",
    program: Path | None = None,
    data: Path | None = None,
    result_addr: str = "0000200",
    expected: str = "25",
    check_result: str = "1",
    max_cycles: str = "1000",
    out_dir: Path | None = None,
    oss_root: Path | None = None,
    open_wave: str = "none",
    schematic: bool = False,
) -> dict[str, object]:
    program = program or (TB_DIR / "array_sum_program.hex")
    data = data or (TB_DIR / "array_sum_data.hex")
    oss_root = oss_root or default_oss_root()
    out_dir = out_dir or (DEFAULT_RUN_ROOT / run_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "run.log"
    log_file.write_text("", encoding="utf-8")

    iverilog = tool_path("iverilog", oss_root)
    vvp = tool_path("vvp", oss_root)
    vcd2fst = tool_path("vcd2fst", oss_root)
    wave_viewer = tool_path(open_wave, oss_root) if open_wave != "none" else None

    sim_path = out_dir / "cpu_tb.vvp"
    vcd_path = out_dir / "cpu_tb.vcd"
    fst_path = out_dir / "cpu_tb.fst"
    report_path = out_dir / "result.json"
    for stale_path in (
        sim_path,
        vcd_path,
        fst_path,
        report_path,
        out_dir / "summary.json",
        out_dir / "index.html",
        out_dir / "cpu_schematic.dot",
        out_dir / "cpu_schematic.svg",
    ):
        stale_path.unlink(missing_ok=True)

    proc = run_tool(
        iverilog,
        [
            "-g2012",
            "-Wall",
            "-s",
            "cpu_tb",
            "-o",
            str(sim_path),
            *[str(path) for path in RTL_SOURCES],
        ],
        REPO_ROOT,
        log_file,
        oss_root,
    )
    if proc.returncode == 0:
        proc = run_tool(
            vvp,
            [
                str(sim_path),
                f"+PROGRAM_HEX={program}",
                f"+DATA_HEX={data}",
                f"+RESULT_ADDR={result_addr}",
                f"+EXPECTED={expected}",
                f"+CHECK_RESULT={check_result}",
                f"+MAX_CYCLES={max_cycles}",
                f"+VCD={vcd_path}",
                f"+REPORT={report_path}",
            ],
            REPO_ROOT,
            log_file,
            oss_root,
        )

    if vcd_path.exists() and (Path(vcd2fst).exists() or shutil.which(vcd2fst) is not None):
        run_tool(vcd2fst, [str(vcd_path), str(fst_path)], REPO_ROOT, log_file, oss_root)

    maybe_generate_schematic(oss_root, out_dir, log_file, schematic)

    result = {
        "run_name": run_name,
        "returncode": proc.returncode,
        "program_hex": str(program),
        "data_hex": str(data),
        "vcd": str(vcd_path) if vcd_path.exists() else None,
        "fst": str(fst_path) if fst_path.exists() else None,
        "report": str(report_path) if report_path.exists() else None,
        "log": str(log_file),
        "schematic_svg": str(out_dir / "cpu_schematic.svg") if (out_dir / "cpu_schematic.svg").exists() else None,
        "schematic_dot": str(out_dir / "cpu_schematic.dot") if (out_dir / "cpu_schematic.dot").exists() else None,
        "oss_root": str(oss_root) if oss_root else None,
    }
    html_path = write_html_index(out_dir, result, report_path)
    result["html"] = str(html_path)

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if wave_viewer is not None and vcd_path.exists():
        subprocess.Popen([wave_viewer, str(fst_path if fst_path.exists() else vcd_path)])

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="array_sum")
    parser.add_argument("--program", type=Path, default=TB_DIR / "array_sum_program.hex")
    parser.add_argument("--data", type=Path, default=TB_DIR / "array_sum_data.hex")
    parser.add_argument("--result-addr", default="0000200")
    parser.add_argument("--expected", default="25")
    parser.add_argument("--check-result", choices=("0", "1"), default="1")
    parser.add_argument("--max-cycles", default="1000")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--oss-root", type=Path, default=None)
    parser.add_argument("--oss-bin", type=Path, default=None, help="Deprecated; use --oss-root.")
    parser.add_argument("--open-wave", choices=("none", "surfer", "gtkwave"), default="none")
    parser.add_argument("--schematic", action="store_true")
    args = parser.parse_args()

    oss_root = args.oss_root
    if oss_root is None and args.oss_bin is not None:
        oss_root = args.oss_bin.parent if args.oss_bin.name == "bin" else args.oss_bin

    result = run_simulation(
        run_name=args.run_name,
        program=args.program,
        data=args.data,
        result_addr=args.result_addr,
        expected=args.expected,
        check_result=args.check_result,
        max_cycles=args.max_cycles,
        out_dir=args.out_dir,
        oss_root=oss_root,
        open_wave=args.open_wave,
        schematic=args.schematic,
    )
    print(json.dumps(result, indent=2))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
