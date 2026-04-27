#!/usr/bin/env python3
"""Run the AMB RTL CPU testbench with OSS CAD Suite-compatible tools."""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from assembler.resources import resolve_oss_root


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[3]

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

GTKW_SIGNALS = [
    "cpu_tb.clk",
    "cpu_tb.reset",
    "cpu_tb.debug_halt",
    "cpu_tb.debug_IC[27:0]",
    "cpu_tb.debug_instr[15:0]",
    "cpu_tb.debug_opcode[6:0]",
    "cpu_tb.debug_RegWrite",
    "cpu_tb.debug_RegDest[1:0]",
    "cpu_tb.debug_DmemReadEn",
    "cpu_tb.debug_DmemWriteEn",
    "cpu_tb.debug_DataAddress[27:0]",
    "cpu_tb.debug_DataMemoryRead[27:0]",
    "cpu_tb.debug_DataMemoryWrite[27:0]",
    "cpu_tb.debug_OperandA[27:0]",
    "cpu_tb.debug_OperandB[27:0]",
    "cpu_tb.debug_ALURes[27:0]",
    "cpu_tb.debug_zero",
    "cpu_tb.debug_altb",
    "cpu_tb.debug_WillBranch",
    "cpu_tb.live_result[27:0]",
    "cpu_tb.actual[27:0]",
    "cpu_tb.actual_valid",
]


def default_oss_root() -> Path | None:
    return resolve_oss_root(REPO_ROOT)


def tool_path(name: str, oss_root: Path | None) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    if oss_root is not None:
        candidate = oss_root / "bin" / f"{name}{suffix}"
        if candidate.exists():
            return str(candidate)
    return shutil.which(f"{name}{suffix}") or shutil.which(name) or name


def tool_environment(oss_root: Path | None) -> dict[str, str] | None:
    if os.name != "nt" or oss_root is None:
        return None

    env = dict(os.environ)
    bin_dir = oss_root / "bin"
    lib_dir = oss_root / "lib"

    extra_path_parts = [str(path) for path in (bin_dir, lib_dir) if path.exists()]
    if extra_path_parts:
        current_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join([*extra_path_parts, current_path]) if current_path else os.pathsep.join(extra_path_parts)

    env["YOSYSHQ_ROOT"] = str(oss_root)
    env["SSL_CERT_FILE"] = str(oss_root / "etc" / "cacert.pem")
    env["PYTHON_EXECUTABLE"] = str(lib_dir / "python3.exe")
    env["QT_PLUGIN_PATH"] = str(lib_dir / "qt5" / "plugins")
    env["QT_LOGGING_RULES"] = "*=false"
    env["GTK_EXE_PREFIX"] = str(oss_root)
    env["GTK_DATA_PREFIX"] = str(oss_root)
    env["GDK_PIXBUF_MODULEDIR"] = str(lib_dir / "gdk-pixbuf-2.0" / "2.10.0" / "loaders")
    env["GDK_PIXBUF_MODULE_FILE"] = str(lib_dir / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache")
    env["OPENFPGALOADER_SOJ_DIR"] = str(oss_root / "share" / "openFPGALoader")
    return env


def command_for_tool(tool: str, args: list[str], oss_root: Path | None) -> tuple[list[str] | str, bool]:
    tool_candidate = Path(tool)
    if tool_candidate.exists():
        return [str(tool_candidate), *args], False
    if os.name != "nt" or oss_root is None:
        return [tool, *args], False
    env_bat = oss_root / "environment.bat"
    if not env_bat.exists():
        return [tool, *args], False
    cmdline = subprocess.list2cmdline([tool, *args])
    return ["cmd.exe", "/d", "/s", "/c", f'call "{env_bat}" && {cmdline}'], False


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
        env=tool_environment(oss_root),
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


def read_json_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def truthy(value: object) -> bool:
    return value is True or value == 1 or value == "1" or value == "true"


def classify_run(
    *,
    returncode: int,
    check_result: str,
    report_data: dict[str, object],
) -> tuple[str, str, str]:
    run_mode = "validation" if check_result == "1" else "inspection"
    if run_mode == "validation":
        if report_data:
            if truthy(report_data.get("pass")):
                return run_mode, "pass", "Benchmark pass"
            return run_mode, "fail", "Benchmark fail"
        return run_mode, "error", "Run failed"

    if returncode != 0:
        return run_mode, "error", "Run failed"

    if truthy(report_data.get("halt")):
        return run_mode, "ok", "Trace complete"
    return run_mode, "warn", "Trace stopped"


def write_gtkw_save(out_dir: Path, wave_path: Path) -> Path:
    gtkw_path = out_dir / "cpu_trace.gtkw"
    lines = [
        f'[dumpfile] "{wave_path.name}"',
        '[timestart] 0',
        '[size] 1400 820',
        '[signals_width] 280',
        '[sst_width] 320',
        '@28',
        '* Core trace',
        *GTKW_SIGNALS,
        '',
    ]
    gtkw_path.write_text("\n".join(lines), encoding="utf-8")
    return gtkw_path


def html_escape(value: object) -> str:
    return html.escape("" if value is None else str(value))


def hex_or_dash(report_data: dict[str, object], key: str) -> str:
    value = report_data.get(key)
    return "-" if value in (None, "") else html_escape(value)


def write_html_index(out_dir: Path, result: dict[str, object], report_path: Path) -> Path:
    html_path = out_dir / "index.html"
    report_data = result.get("testbench")
    if not isinstance(report_data, dict):
        report_data = {}
    report_text = report_path.read_text(encoding="utf-8") if report_path.exists() else "{}\n"
    schematic_svg = out_dir / "cpu_schematic.svg"
    schematic_block = (
        '<section class="panel"><h2>CPU schematic</h2><img src="cpu_schematic.svg" alt="CPU schematic"></section>'
        if schematic_svg.exists()
        else '<section class="panel"><h2>CPU schematic</h2><p>Not generated for this run.</p></section>'
    )
    mode_label = "Benchmark validation" if result.get("run_mode") == "validation" else "RTL inspection"
    validation_block = ""
    if result.get("run_mode") == "validation":
        validation_block = f"""
    <div class="metric">
      <span>Expected</span>
      <strong>0x{hex_or_dash(report_data, "expected_hex")}</strong>
    </div>
    <div class="metric">
      <span>Actual</span>
      <strong>0x{hex_or_dash(report_data, "actual_hex")}</strong>
    </div>
    <div class="metric">
      <span>Result address</span>
      <strong>0x{hex_or_dash(report_data, "result_addr_hex")}</strong>
    </div>
"""
    artifact_links = [
        ("Result JSON", "result.json", result.get("report")),
        ("Summary JSON", "summary.json", out_dir / "summary.json"),
        ("Run log", "run.log", result.get("log")),
        ("VCD", "cpu_tb.vcd", result.get("vcd")),
        ("FST", "cpu_tb.fst", result.get("fst")),
        ("GTKWave layout", "cpu_trace.gtkw", result.get("gtkw")),
        ("Schematic SVG", "cpu_schematic.svg", result.get("schematic_svg")),
    ]
    artifact_html = "\n".join(
        f'<a href="{href}">{html_escape(label)}</a>'
        for label, href, exists_value in artifact_links
        if exists_value
    )
    html_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AMB RTL Run: {html.escape(str(result["run_name"]))}</title>
  <style>
    :root {{ --ink: #14212a; --muted: #5f7280; --line: #b9cedb; --blue: #0b84d8; --green: #168a55; --red: #b42318; --amber: #b45309; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f8fbfd; color: var(--ink); font-family: "Segoe UI", Verdana, sans-serif; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 34px; }}
    header {{ display: grid; gap: 14px; padding: 28px 0 24px; border-bottom: 1px solid var(--line); }}
    h1 {{ margin: 0; font-size: clamp(34px, 7vw, 72px); line-height: .95; letter-spacing: -.06em; }}
    h2 {{ margin: 0 0 12px; font-size: 20px; }}
    a {{ color: var(--blue); font-weight: 800; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .eyebrow {{ color: var(--muted); font-weight: 800; letter-spacing: .14em; text-transform: uppercase; }}
    .status {{ width: max-content; border-radius: 999px; padding: 8px 13px; color: white; font-weight: 800; background: var(--blue); }}
    .status.pass, .status.ok {{ background: var(--green); }}
    .status.fail, .status.error {{ background: var(--red); }}
    .status.warn {{ background: var(--amber); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric {{ border-top: 2px solid var(--line); padding-top: 10px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 12px; font-weight: 800; letter-spacing: .10em; text-transform: uppercase; }}
    .metric strong {{ display: block; margin-top: 5px; font-size: 20px; overflow-wrap: anywhere; }}
    .panel {{ margin: 24px 0; padding: 20px; border: 1px solid var(--line); border-radius: 14px; background: white; box-shadow: 0 10px 28px rgba(20, 45, 60, .08); }}
    .links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .links a {{ border: 1px solid var(--blue); border-radius: 999px; padding: 8px 12px; background: #eef8ff; }}
    .paths {{ display: grid; gap: 8px; color: #344653; font-family: "Cascadia Mono", Consolas, monospace; font-size: 13px; }}
    details {{ margin-top: 14px; }}
    summary {{ cursor: pointer; font-weight: 800; color: var(--blue); }}
    pre {{ overflow: auto; background: #14212a; color: #e6edf3; padding: 1rem; border-radius: 10px; font-family: "Cascadia Mono", Consolas, monospace; }}
    img {{ max-width: 100%; background: white; }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">{html_escape(mode_label)}</div>
      <h1>{html_escape(result.get("status_label", "RTL run"))}</h1>
      <div class="status {html_escape(result.get("status_kind", ""))}">returncode={html_escape(result.get("returncode"))}</div>
    </header>
    <section class="grid">
      <div class="metric"><span>Cycles</span><strong>{html_escape(report_data.get("cycles", "-"))}</strong></div>
      <div class="metric"><span>Halt</span><strong>{html_escape(report_data.get("halt", "-"))}</strong></div>
      <div class="metric"><span>Final IC</span><strong>{html_escape(report_data.get("ic", "-"))}</strong></div>
      <div class="metric"><span>Mode</span><strong>{html_escape(result.get("run_mode", "-"))}</strong></div>
      {validation_block}
    </section>
    <section class="panel">
      <h2>Run inputs</h2>
      <div class="paths">
        <div>Program: {html_escape(result.get("program_hex"))}</div>
        <div>Data: {html_escape(result.get("data_hex"))}</div>
        <div>Data source: {html_escape(result.get("data_source", "unspecified"))}</div>
      </div>
    </section>
    <section class="panel">
      <h2>Artifacts</h2>
      <div class="links">{artifact_html}</div>
      <p>Use <strong>Open Waveform</strong> in the app for the full GTKWave/Surfer view. This report keeps the run readable and links the raw files.</p>
    </section>
    {schematic_block}
    <section class="panel">
      <h2>Raw details</h2>
      <details>
        <summary>Show result.json</summary>
        <pre>{html.escape(report_text)}</pre>
      </details>
    </section>
  </main>
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
    data_source: str | None = None,
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
        out_dir / "cpu_trace.gtkw",
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

    wave_path = fst_path if fst_path.exists() else vcd_path
    gtkw_path = write_gtkw_save(out_dir, wave_path) if wave_path.exists() else None
    report_data = read_json_file(report_path)
    run_mode, status_kind, status_label = classify_run(
        returncode=proc.returncode,
        check_result=check_result,
        report_data=report_data,
    )
    result = {
        "run_name": run_name,
        "returncode": proc.returncode,
        "run_mode": run_mode,
        "status_kind": status_kind,
        "status_label": status_label,
        "program_hex": str(program),
        "data_hex": str(data),
        "data_source": data_source or ("Benchmark data image" if check_result == "1" else "Data image"),
        "vcd": str(vcd_path) if vcd_path.exists() else None,
        "fst": str(fst_path) if fst_path.exists() else None,
        "gtkw": str(gtkw_path) if gtkw_path is not None and gtkw_path.exists() else None,
        "report": str(report_path) if report_path.exists() else None,
        "log": str(log_file),
        "schematic_svg": str(out_dir / "cpu_schematic.svg") if (out_dir / "cpu_schematic.svg").exists() else None,
        "schematic_dot": str(out_dir / "cpu_schematic.dot") if (out_dir / "cpu_schematic.dot").exists() else None,
        "oss_root": str(oss_root) if oss_root else None,
        "testbench": report_data,
        "artifacts": {},
    }
    result["artifacts"] = {
        "html": str(out_dir / "index.html"),
        "result_json": result["report"],
        "summary_json": str(out_dir / "summary.json"),
        "run_log": result["log"],
        "vcd": result["vcd"],
        "fst": result["fst"],
        "gtkw": result["gtkw"],
        "schematic_svg": result["schematic_svg"],
    }
    html_path = write_html_index(out_dir, result, report_path)
    result["html"] = str(html_path)
    result["artifacts"]["html"] = str(html_path)  # type: ignore[index]

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if wave_viewer is not None and wave_path.exists():
        if Path(wave_viewer).name.startswith("gtkwave") and gtkw_path is not None:
            subprocess.Popen([wave_viewer, "-a", str(gtkw_path), str(wave_path)])
        else:
            subprocess.Popen([wave_viewer, str(wave_path)])

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", default="array_sum")
    parser.add_argument("--program", type=Path, default=TB_DIR / "array_sum_program.hex")
    parser.add_argument("--data", type=Path, default=TB_DIR / "array_sum_data.hex")
    parser.add_argument("--data-source", default=None)
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
        data_source=args.data_source,
    )
    print(json.dumps(result, indent=2))
    return int(result["returncode"])


if __name__ == "__main__":
    raise SystemExit(main())
