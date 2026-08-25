from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from gis2dgs import __version__
from gis2dgs.cli.workspace import (
    classify_file,
    load_and_run,
    suggest_mapping_for_loaded,
    suggest_mapping_for_uri,
)
from gis2dgs.config import load_project_config
from gis2dgs.dgs import DgsError, inspect_excel_template
from gis2dgs.input import InputError, InputKind, InputReaderFactory, discover_schema
from gis2dgs.input.compact import env_sample_rows
from gis2dgs.pipeline import run_conversion


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gis2dgs",
        description="Universal electrical-network data to DIgSILENT DGS converter",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")

    inspect_input = commands.add_parser(
        "inspect-input",
        help="Inspect tables/layers and fields of an input file or database",
    )
    inspect_input.add_argument("source")
    inspect_input.add_argument(
        "--kind",
        choices=[kind.value for kind in InputKind],
        default=InputKind.AUTO.value,
    )
    inspect_input.add_argument("--output", type=Path)
    inspect_input.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Max rows per table for large files (0 = full). Default GIS2DGS_SAMPLE_ROWS or 100k.",
    )

    suggest = commands.add_parser(
        "suggest-mapping",
        help="Propose mapping YAML from a file/folder using NSGA-II + TOPSIS (does not write DGS)",
    )
    suggest.add_argument("source")
    suggest.add_argument(
        "--kind",
        choices=[kind.value for kind in InputKind],
        default=InputKind.AUTO.value,
    )
    suggest.add_argument("--output", type=Path, default=Path("output/suggested_mapping.yaml"))
    suggest.add_argument("--sample-rows", type=int, default=None)
    suggest.add_argument(
        "--llm",
        action="store_true",
        help="Optional OpenAI-compatible refinement via GIS2DGS_LLM_URL and GIS2DGS_LLM_API_KEY",
    )
    suggest.add_argument(
        "--modality",
        choices=["nsga_topsis", "greedy", "llm", "pareto"],
        default="nsga_topsis",
        help="Decision modality for selecting a mapping from the Pareto front",
    )
    suggest.add_argument(
        "--pareto-index",
        type=int,
        default=None,
        help="Explicit Pareto front index (requires --modality pareto)",
    )
    suggest.add_argument(
        "--weights",
        default=None,
        help="TOPSIS weights, e.g. coverage=0.3,lexical=0.2,type_consistency=0.15,...",
    )

    load = commands.add_parser(
        "load",
        help="Detect file type and run inspect → mapping → validated DGS",
    )
    load.add_argument("source")
    load.add_argument("--json", action="store_true", dest="as_json")
    load.add_argument(
        "--output-dir",
        type=Path,
        help="Working directory for scaffolded project.yaml (default output/loaded/<name>)",
    )
    load.add_argument("--sample-rows", type=int, default=None)
    load.add_argument("--llm", action="store_true")
    load.add_argument("--debug", action="store_true")
    load.add_argument(
        "--modality",
        choices=["nsga_topsis", "greedy", "llm", "pareto"],
        default="nsga_topsis",
    )
    load.add_argument("--pareto-index", type=int, default=None)
    load.add_argument(
        "--weights",
        default=None,
        help="TOPSIS weights, e.g. coverage=0.3,lexical=0.2,...",
    )
    load.add_argument(
        "--strategy",
        choices=["auto", "full_mapped", "network_core", "compact_lines"],
        default="auto",
        help="Multimodal conversion strategy after mapping selection",
    )

    convert = commands.add_parser(
        "convert",
        help="Run the complete configured input → validated DGS pipeline",
    )
    convert.add_argument("project", type=Path)
    convert.add_argument("--json", action="store_true", dest="as_json")
    convert.add_argument("--debug", action="store_true")

    gui = commands.add_parser(
        "gui",
        help="Open the desktop window to load a source and run the integral flow",
    )
    gui.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not open the file dialog automatically on startup",
    )

    dgs = commands.add_parser("dgs", help="DGS template and serialization utilities")
    dgs_commands = dgs.add_subparsers(dest="dgs_command")
    inspect = dgs_commands.add_parser(
        "inspect-template",
        help="Inspect an exported DGS Excel workbook and typed headers",
    )
    inspect.add_argument("template", type=Path)
    inspect.add_argument("--output", type=Path)
    return parser


def _write_or_print_yaml(payload: dict[str, object], output: Path | None) -> None:
    text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    if output is None:
        print(text, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inspect-input":
        try:
            budget = args.sample_rows if args.sample_rows is not None else env_sample_rows()
            options: dict[str, object] = {"copy_frame": False, "compact": True}
            if budget is not None and budget > 0:
                options["sample_rows"] = budget
            reader = InputReaderFactory.create(
                args.source,
                kind=InputKind(args.kind),
                options=options,
            )
            schema = discover_schema(reader.read(), sample_rows=budget)
        except InputError as exc:
            parser.exit(2, f"ERROR: {exc}\n")
        _write_or_print_yaml(schema.as_dict(), args.output)
        return

    if args.command == "suggest-mapping":
        if "://" in str(args.source):
            outcome = suggest_mapping_for_uri(
                args.source,
                output=args.output,
                kind=InputKind(args.kind),
                sample_rows=args.sample_rows,
                use_llm=args.llm,
                modality=args.modality,
                weights=args.weights,
                pareto_index=args.pareto_index,
            )
        else:
            loaded = classify_file(Path(args.source))
            outcome = suggest_mapping_for_loaded(
                loaded,
                output=args.output,
                sample_rows=args.sample_rows,
                use_llm=args.llm,
                modality=args.modality,
                weights=args.weights,
                pareto_index=args.pareto_index,
            )
        if not outcome.success:
            parser.exit(2, f"ERROR: {outcome.message}\n")
        mapping = outcome.payload.get("mapping")
        if not isinstance(mapping, dict):
            parser.exit(2, "ERROR: mapping payload missing\n")
        return

    if args.command == "load":
        try:
            outcome = load_and_run(
                args.source,
                work_dir=args.output_dir,
                sample_rows=args.sample_rows,
                use_llm=args.llm,
                modality=args.modality,
                weights=args.weights,
                pareto_index=args.pareto_index,
                strategy=args.strategy,
            )
        except Exception as exc:
            if args.debug:
                raise
            parser.exit(2, f"ERROR [{type(exc).__name__}]: {exc}\n")
        if not outcome.success:
            parser.exit(2, f"ERROR: {outcome.message}\n")
        if args.as_json:
            print(json.dumps(outcome.payload, indent=2, ensure_ascii=False, default=str))
        else:
            print(outcome.message)
            _write_or_print_yaml(
                {k: v for k, v in outcome.payload.items() if k != "schema"},
                None,
            )
        return

    if args.command == "convert":
        project = load_project_config(args.project)
        try:
            result = run_conversion(project)
        except Exception as exc:
            if args.debug:
                raise
            parser.exit(2, f"ERROR [{type(exc).__name__}]: {exc}\n")
        payload = result.as_dict()
        if args.as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            _write_or_print_yaml(payload, None)
        return

    if args.command == "dgs" and args.dgs_command == "inspect-template":
        try:
            report = inspect_excel_template(args.template)
        except DgsError as exc:
            parser.exit(2, f"ERROR: {exc}\n")
        _write_or_print_yaml(report.as_dict(), args.output)
        return

    if args.command in {None, "gui"}:
        from gis2dgs.cli.gui import launch_gui

        prompt_on_start = True
        if args.command == "gui":
            prompt_on_start = not args.no_prompt
        launch_gui(prompt_on_start=prompt_on_start)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
