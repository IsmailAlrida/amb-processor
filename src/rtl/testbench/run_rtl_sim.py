#!/usr/bin/env python3
"""Run the AMB RTL CPU testbench with OSS CAD Suite-compatible tools."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import html
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, TypedDict

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from assembler.resources import app_root as resource_app_root, resolve_oss_root


class StartupOptions(TypedDict, total=False):
    startupinfo: Any
    creationflags: int


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return resource_app_root()
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

DARWIN_DIRECT_TOOL_NAMES = {"iverilog", "vvp", "vcd2fst", "surfer"}


def default_oss_root() -> Path | None:
    return resolve_oss_root(REPO_ROOT)


def is_macos() -> bool:
    return platform.system() == "Darwin"


def _oss_tool_candidates(name: str, oss_root: Path, *, direct_darwin: bool | None = None) -> tuple[Path, ...]:
    suffix = ".exe" if os.name == "nt" else ""
    direct_darwin = is_macos() if direct_darwin is None else direct_darwin
    if direct_darwin:
        return (
            oss_root / "libexec" / name,
            oss_root / "bin" / name,
        )
    return (oss_root / "bin" / f"{name}{suffix}",)


def _existing_oss_tool(name: str, oss_root: Path, *, direct_darwin: bool | None = None) -> Path | None:
    for candidate in _oss_tool_candidates(name, oss_root, direct_darwin=direct_darwin):
        if candidate.exists():
            return candidate
    return None


def tool_path(name: str, oss_root: Path | None) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    if oss_root is not None:
        candidate = _existing_oss_tool(
            name,
            oss_root,
            direct_darwin=is_macos() and name in DARWIN_DIRECT_TOOL_NAMES,
        )
        if candidate is not None:
            return str(candidate)
    return shutil.which(f"{name}{suffix}") or shutil.which(name) or name


def tool_environment(oss_root: Path | None) -> dict[str, str] | None:
    if oss_root is None:
        return None

    env = dict(os.environ)
    bin_dir = oss_root / "bin"
    lib_dir = oss_root / "lib"
    libexec_dir = oss_root / "libexec"

    if os.name != "nt" and not is_macos():
        return None

    path_dirs = (bin_dir, libexec_dir, lib_dir) if is_macos() else (bin_dir, lib_dir)
    extra_path_parts = [str(path) for path in path_dirs if path.exists()]
    if extra_path_parts:
        current_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join([*extra_path_parts, current_path]) if current_path else os.pathsep.join(extra_path_parts)

    env["YOSYSHQ_ROOT"] = str(oss_root)
    env["SSL_CERT_FILE"] = str(oss_root / "etc" / "cacert.pem")
    if is_macos():
        existing_dyld_library_path = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = (
            os.pathsep.join([str(lib_dir), existing_dyld_library_path])
            if existing_dyld_library_path
            else str(lib_dir)
        )
        existing_dyld_fallback = env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        env["DYLD_FALLBACK_LIBRARY_PATH"] = (
            os.pathsep.join([str(lib_dir), existing_dyld_fallback])
            if existing_dyld_fallback
            else str(lib_dir)
        )
        fonts_dir = oss_root / "etc" / "fonts"
        if fonts_dir.exists():
            env["FONTCONFIG_PATH"] = str(fonts_dir)
        return env

    env["PYTHON_EXECUTABLE"] = str(lib_dir / "python3.exe")
    env["QT_PLUGIN_PATH"] = str(lib_dir / "qt5" / "plugins")
    env["QT_LOGGING_RULES"] = "*=false"
    env["GTK_EXE_PREFIX"] = str(oss_root)
    env["GTK_DATA_PREFIX"] = str(oss_root)
    env["GDK_PIXBUF_MODULEDIR"] = str(lib_dir / "gdk-pixbuf-2.0" / "2.10.0" / "loaders")
    env["GDK_PIXBUF_MODULE_FILE"] = str(lib_dir / "gdk-pixbuf-2.0" / "2.10.0" / "loaders.cache")
    env["OPENFPGALOADER_SOJ_DIR"] = str(oss_root / "share" / "openFPGALoader")
    return env


def _get_windows_dll_directory() -> str | None:
    if os.name != "nt":
        return None

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetDllDirectoryW.argtypes = [ctypes.c_uint32, ctypes.c_wchar_p]
    kernel32.GetDllDirectoryW.restype = ctypes.c_uint32

    size = 32768
    buffer = ctypes.create_unicode_buffer(size)
    length = kernel32.GetDllDirectoryW(size, buffer)
    if length == 0:
        return None
    if length >= size:
        buffer = ctypes.create_unicode_buffer(length + 1)
        length = kernel32.GetDllDirectoryW(length + 1, buffer)
        if length == 0:
            return None
    return buffer.value or None


def _set_windows_dll_directory(path: str | None) -> None:
    if os.name != "nt":
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel32.SetDllDirectoryW.restype = ctypes.c_bool
    if not kernel32.SetDllDirectoryW(path):
        raise ctypes.WinError(ctypes.get_last_error())


@contextlib.contextmanager
def clean_child_dll_search():
    """Stop PyInstaller's DLL directory override from leaking into child tools."""
    if os.name != "nt":
        yield
        return

    previous = _get_windows_dll_directory()
    _set_windows_dll_directory(None)
    try:
        yield
    finally:
        _set_windows_dll_directory(previous)


def _startup_options(*, suppress_console: bool, hide_window: bool = False) -> StartupOptions:
    if os.name != "nt":
        return {}

    options: StartupOptions = {}
    if hide_window:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        options["startupinfo"] = startupinfo
    if suppress_console:
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return options


def tool_working_directory(cwd: Path, oss_root: Path | None) -> Path:
    if os.name == "nt" and getattr(sys, "frozen", False) and oss_root is not None and oss_root.exists():
        return oss_root
    return cwd


def format_returncode(returncode: int) -> str:
    if returncode < 0:
        return f"{returncode} (0x{returncode & 0xFFFFFFFF:08X})"
    if returncode >= 256:
        return f"{returncode} (0x{returncode:08X})"
    return str(returncode)


def _path_head(env: dict[str, str] | None, max_parts: int = 4) -> str:
    raw_path = (env or os.environ).get("PATH", "")
    if not raw_path:
        return ""
    return os.pathsep.join(raw_path.split(os.pathsep)[:max_parts])


def _display_command(cmd: list[str] | str) -> str:
    if isinstance(cmd, str):
        return cmd
    if os.name == "nt":
        return subprocess.list2cmdline(cmd)
    return shlex.join(cmd)


def _darwin_tool_args(tool: Path, args: list[str], oss_root: Path | None) -> list[str]:
    if not is_macos() or oss_root is None or tool.name != "iverilog":
        return args

    vvp = _existing_oss_tool("vvp", oss_root, direct_darwin=True)
    if vvp is None:
        return args
    return ["-p", f"VVP_EXECUTABLE={vvp}", *args]


def command_for_tool(tool: str, args: list[str], oss_root: Path | None) -> tuple[list[str] | str, bool]:
    tool_candidate = Path(tool)
    if tool_candidate.exists():
        return [str(tool_candidate), *_darwin_tool_args(tool_candidate, args, oss_root)], False
    if os.name != "nt" or oss_root is None:
        return [tool, *args], False
    env_bat = oss_root / "environment.bat"
    if not env_bat.exists():
        return [tool, *args], False
    cmdline = subprocess.list2cmdline([tool, *args])
    return ["cmd.exe", "/d", "/s", "/c", f'call "{env_bat}" && {cmdline}'], False


def popen_tool(
    tool: str,
    args: list[str],
    cwd: Path,
    oss_root: Path | None,
    *,
    hide_console: bool = False,
) -> subprocess.Popen:
    env = tool_environment(oss_root)
    actual_cwd = tool_working_directory(cwd, oss_root)
    launch_args = args
    if Path(tool).name.lower().startswith("surfer") and args:
        wave_path = Path(args[-1]).resolve()
        actual_cwd = wave_path.parent
        command_file = write_surfer_command_file(actual_cwd)
        write_surfer_config(actual_cwd)
        launch_args = ["--command-file", str(command_file), str(wave_path)]

    cmd, use_shell = command_for_tool(tool, launch_args, oss_root)
    with clean_child_dll_search():
        return subprocess.Popen(
            cmd,
            cwd=actual_cwd,
            env=env,
            shell=use_shell,
            **_startup_options(suppress_console=hide_console),
        )


def run_tool(
    tool: str,
    args: list[str],
    cwd: Path,
    log_file: Path,
    oss_root: Path | None,
) -> subprocess.CompletedProcess[str]:
    cmd, use_shell = command_for_tool(tool, args, oss_root)
    env = tool_environment(oss_root)
    actual_cwd = tool_working_directory(cwd, oss_root)
    with clean_child_dll_search():
        proc = subprocess.run(
            cmd,
            cwd=actual_cwd,
            env=env,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=use_shell,
            **_startup_options(suppress_console=True, hide_window=True),
        )
    printable = _display_command(cmd)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("$ " + printable + "\n")
        handle.write(f"[cwd {actual_cwd}]\n")
        if oss_root is not None:
            handle.write(f"[oss_root {oss_root}]\n")
        path_head = _path_head(env)
        if path_head:
            handle.write(f"[path_head {path_head}]\n")
        handle.write(proc.stdout)
        if proc.stdout and not proc.stdout.endswith("\n"):
            handle.write("\n")
        handle.write(f"[exit {format_returncode(proc.returncode)}]\n\n")
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


def stage_hex_input(source: Path, destination: Path) -> Path:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source != destination:
        shutil.copy2(source, destination)
    return destination


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


def write_surfer_config(out_dir: Path) -> Path:
    config_path = out_dir / ".surfer" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        'autoload_sibling_state_files = "Never"\n'
        "\n"
        "[layout]\n"
        'hierarchy_style = "Tree"\n'
        'parameter_display_location = "None"\n'
        "show_empty_scopes = false\n",
        encoding="utf-8",
    )
    return config_path


def write_surfer_command_file(out_dir: Path) -> Path:
    command_path = out_dir / "cpu_trace.sucl"
    command_path.write_text("preference_set_hierarchy_style Tree\n", encoding="utf-8")
    return command_path


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
      <p>Use <strong>Open Waveform</strong> in the app for the full Surfer view. This report keeps the run readable and links the raw files.</p>
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
    program = (program or (TB_DIR / "array_sum_program.hex")).expanduser().resolve()
    data = (data or (TB_DIR / "array_sum_data.hex")).expanduser().resolve()
    oss_root = (oss_root or default_oss_root())
    if oss_root is not None:
        oss_root = oss_root.expanduser().resolve()
    out_dir = (out_dir or (DEFAULT_RUN_ROOT / run_name)).expanduser().resolve()
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
    staged_program = stage_hex_input(program, out_dir / "program.hex")
    staged_data = stage_hex_input(data, out_dir / "data.hex")
    waveform_conversion: dict[str, object] | None = None
    for stale_path in (
        sim_path,
        vcd_path,
        fst_path,
        report_path,
        out_dir / "summary.json",
        out_dir / "index.html",
        out_dir / "cpu_trace.sucl",
        out_dir / ".surfer" / "config.toml",
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
                f"+PROGRAM_HEX={staged_program}",
                f"+DATA_HEX={staged_data}",
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
        conversion_proc = run_tool(vcd2fst, [str(vcd_path), str(fst_path)], REPO_ROOT, log_file, oss_root)
        waveform_conversion = {
            "tool": vcd2fst,
            "returncode": conversion_proc.returncode,
            "returncode_label": format_returncode(conversion_proc.returncode),
            "output": str(fst_path),
        }
        if conversion_proc.returncode != 0:
            with log_file.open("a", encoding="utf-8") as handle:
                handle.write(
                    "[required vcd2fst failed; packaged FST conversion did not complete]\n"
                    f"[exit {format_returncode(conversion_proc.returncode)}]\n\n"
                )
    elif vcd_path.exists():
        waveform_conversion = {
            "tool": vcd2fst,
            "returncode": None,
            "returncode_label": "unavailable",
            "output": str(fst_path),
        }
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"[required vcd2fst unavailable: {vcd2fst}]\n\n")

    maybe_generate_schematic(oss_root, out_dir, log_file, schematic)

    wave_path = fst_path if fst_path.exists() else vcd_path
    report_data = read_json_file(report_path)
    run_mode, status_kind, status_label = classify_run(
        returncode=proc.returncode,
        check_result=check_result,
        report_data=report_data,
    )
    artifacts: dict[str, object] = {
        "html": str(out_dir / "index.html"),
        "result_json": str(report_path) if report_path.exists() else None,
        "summary_json": str(out_dir / "summary.json"),
        "run_log": str(log_file),
        "vcd": str(vcd_path) if vcd_path.exists() else None,
        "fst": str(fst_path) if fst_path.exists() else None,
        "schematic_svg": str(out_dir / "cpu_schematic.svg") if (out_dir / "cpu_schematic.svg").exists() else None,
    }
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
        "report": str(report_path) if report_path.exists() else None,
        "log": str(log_file),
        "schematic_svg": str(out_dir / "cpu_schematic.svg") if (out_dir / "cpu_schematic.svg").exists() else None,
        "schematic_dot": str(out_dir / "cpu_schematic.dot") if (out_dir / "cpu_schematic.dot").exists() else None,
        "oss_root": str(oss_root) if oss_root else None,
        "waveform_conversion": waveform_conversion,
        "testbench": report_data,
        "artifacts": artifacts,
    }
    html_path = write_html_index(out_dir, result, report_path)
    result["html"] = str(html_path)
    artifacts["html"] = str(html_path)

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if wave_viewer is not None and wave_path.exists():
        popen_tool(wave_viewer, [str(wave_path)], REPO_ROOT, oss_root, hide_console=True)

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
    parser.add_argument("--open-wave", choices=("none", "surfer"), default="none")
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
    returncode = result.get("returncode", 1)
    return returncode if isinstance(returncode, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
