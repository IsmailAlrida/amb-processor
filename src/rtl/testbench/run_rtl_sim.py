#!/usr/bin/env python3
"""Run the AMB RTL CPU testbench with OSS CAD Suite-compatible tools."""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RTL_DIR = REPO_ROOT / "src" / "rtl"
TB_DIR = RTL_DIR / "testbench"
PROCESSOR_DIR = RTL_DIR / "processor"
DEFAULT_OSS_BIN = Path("/home/alrida_ismail/downloads/oss-cad-suite/bin")

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


def tool_path(name: str, oss_bin: Path | None) -> str:
    if oss_bin is not None:
        candidate = oss_bin / name
        if candidate.exists():
            return str(candidate)
    return shutil.which(name) or name


def run(cmd: list[str], cwd: Path, log_file: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        handle.write(proc.stdout)
        if proc.stdout and not proc.stdout.endswith("\n"):
            handle.write("\n")
        handle.write(f"[exit {proc.returncode}]\n\n")
    return proc


def maybe_generate_schematic(args: argparse.Namespace, out_dir: Path, log_file: Path) -> None:
    if not args.schematic:
        return

    yosys = tool_path("yosys", args.oss_bin)
    dot = tool_path("dot", args.oss_bin)
    dot_path = out_dir / "cpu_schematic.dot"
    svg_path = out_dir / "cpu_schematic.svg"
    script = (
        "read_verilog -sv "
        + " ".join(str(path) for path in CPU_CORE_SOURCES)
        + f"; hierarchy -top cpu; proc; opt_clean; show -format dot -prefix {out_dir / 'cpu_schematic'} cpu"
    )
    proc = run([yosys, "-p", script], REPO_ROOT, log_file)
    if proc.returncode != 0:
        return
    if dot_path.exists():
        run([dot, "-Tsvg", str(dot_path), "-o", str(svg_path)], REPO_ROOT, log_file)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="array_sum")
    parser.add_argument("--program", type=Path, default=TB_DIR / "array_sum_program.hex")
    parser.add_argument("--data", type=Path, default=TB_DIR / "array_sum_data.hex")
    parser.add_argument("--result-addr", default="0000200")
    parser.add_argument("--expected", default="25")
    parser.add_argument("--max-cycles", default="1000")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--oss-bin", type=Path, default=DEFAULT_OSS_BIN if DEFAULT_OSS_BIN.exists() else None)
    parser.add_argument("--open-wave", choices=("none", "surfer", "gtkwave"), default="none")
    parser.add_argument("--schematic", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir or (REPO_ROOT / "build" / "rtl_sim" / args.run_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_file = out_dir / "run.log"
    log_file.write_text("", encoding="utf-8")

    iverilog = tool_path("iverilog", args.oss_bin)
    vvp = tool_path("vvp", args.oss_bin)
    vcd2fst = tool_path("vcd2fst", args.oss_bin)
    wave_viewer = tool_path(args.open_wave, args.oss_bin) if args.open_wave != "none" else None

    sim_path = out_dir / "cpu_tb.vvp"
    vcd_path = out_dir / "cpu_tb.vcd"
    fst_path = out_dir / "cpu_tb.fst"
    report_path = out_dir / "result.json"

    compile_cmd = [
        iverilog,
        "-g2012",
        "-Wall",
        "-s",
        "cpu_tb",
        "-o",
        str(sim_path),
        *[str(path) for path in RTL_SOURCES],
    ]
    proc = run(compile_cmd, REPO_ROOT, log_file)
    if proc.returncode != 0:
        return proc.returncode

    sim_cmd = [
        vvp,
        str(sim_path),
        f"+PROGRAM_HEX={args.program}",
        f"+DATA_HEX={args.data}",
        f"+RESULT_ADDR={args.result_addr}",
        f"+EXPECTED={args.expected}",
        f"+MAX_CYCLES={args.max_cycles}",
        f"+VCD={vcd_path}",
        f"+REPORT={report_path}",
    ]
    proc = run(sim_cmd, REPO_ROOT, log_file)

    if vcd_path.exists() and (Path(vcd2fst).exists() or shutil.which(vcd2fst) is not None):
        run([vcd2fst, str(vcd_path), str(fst_path)], REPO_ROOT, log_file)

    maybe_generate_schematic(args, out_dir, log_file)

    result = {
        "run_name": args.run_name,
        "returncode": proc.returncode,
        "program_hex": str(args.program),
        "data_hex": str(args.data),
        "vcd": str(vcd_path) if vcd_path.exists() else None,
        "fst": str(fst_path) if fst_path.exists() else None,
        "report": str(report_path) if report_path.exists() else None,
        "log": str(log_file),
        "schematic_svg": str(out_dir / "cpu_schematic.svg") if (out_dir / "cpu_schematic.svg").exists() else None,
        "schematic_dot": str(out_dir / "cpu_schematic.dot") if (out_dir / "cpu_schematic.dot").exists() else None,
    }
    html_path = write_html_index(out_dir, result, report_path)
    result["html"] = str(html_path)

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if wave_viewer is not None and vcd_path.exists():
        subprocess.Popen([wave_viewer, str(fst_path if fst_path.exists() else vcd_path)])

    print(json.dumps(result, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
