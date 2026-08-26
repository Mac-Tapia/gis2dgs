from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from gis2dgs import __version__
from gis2dgs.assist.decision import (
    DEFAULT_TOPSIS_WEIGHTS,
    OBJECTIVE_NAMES,
    DecisionModality,
    normalize_topsis_weights,
)
from gis2dgs.assist.strategies import ConversionStrategy
from gis2dgs.cli.workspace import (
    ExecutionOutcome,
    LoadedFile,
    LoadedFileKind,
    classify_file,
    classify_paths,
    load_and_run_loaded,
    suggest_mapping_for_loaded,
)
from gis2dgs.input import programmed_file_suffixes


def _dialog_filetypes() -> tuple[tuple[str, str], ...]:
    data = " ".join(f"*{suffix}" for suffix in sorted(programmed_file_suffixes()))
    return (
        ("Formatos del conversor", f"*.yaml *.yml {data}"),
        ("Texto CYMDIST / red", "*.txt"),
        ("Proyecto YAML", "*.yaml *.yml"),
        ("Excel", "*.xlsx *.xlsm *.xls"),
        ("CSV / TSV", "*.csv *.tsv"),
        ("Vectorial", "*.shp *.gpkg *.geojson *.json *.gml *.kml"),
        ("Parquet", "*.parquet *.pq"),
        ("SQLite", "*.sqlite *.sqlite3 *.db"),
        ("Backup SQL Server", "*.bak"),
        ("Todos", "*.*"),
    )


_MODALITY_LABELS = {
    DecisionModality.NSGA_TOPSIS.value: "NSGA-II + TOPSIS",
    DecisionModality.GREEDY.value: "Greedy",
    DecisionModality.LLM.value: "LLM (opcional)",
    DecisionModality.PARETO.value: "Índice Pareto",
}

_STRATEGY_LABELS = {
    ConversionStrategy.AUTO.value: "Auto (TOPSIS)",
    ConversionStrategy.FULL_MAPPED.value: "Full mapped",
    ConversionStrategy.NETWORK_CORE.value: "Network core",
    ConversionStrategy.COMPACT_LINES.value: "Compact lines",
}


class ConverterApp(tk.Tk):
    """Desktop window: load a source, decide mapping, run the integral flow."""

    def __init__(self, *, prompt_on_start: bool = False) -> None:
        super().__init__()
        self.title(f"GIS2DGS {__version__}")
        self.minsize(900, 640)
        self.geometry("1040x720")
        self._loaded: LoadedFile | None = None
        self._busy = False
        self._pareto: list[dict] = []
        self._confirmed_mapping: dict | None = None
        self._weight_vars: dict[str, tk.DoubleVar] = {}
        self._build()
        # Solo abre el diálogo si se pide explícitamente (p. ej. --prompt).
        # Por defecto queda la ventana principal y el usuario elige archivo/carpeta.
        if prompt_on_start:
            self.after(200, self._choose_file)

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=8)
        ttk.Label(
            header,
            text="Cargue archivos, decida el mapping y pulse Ejecutar",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "Multiobjetivo (NSGA-II) + multicriterio (TOPSIS) + multimodal "
                "(Pareto / estrategias de conversión). "
                "Proponer mapping abre el frente Pareto; Ejecutar convierte."
            ),
            wraplength=980,
        ).pack(anchor="w", pady=(4, 0))

        file_row = ttk.Frame(self)
        file_row.pack(fill="x", padx=12, pady=8)
        ttk.Button(file_row, text="Cargar archivo…", command=self._choose_file).pack(
            side="left"
        )
        ttk.Button(file_row, text="Cargar varios…", command=self._choose_files).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(file_row, text="Cargar carpeta…", command=self._choose_folder).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(file_row, text="Ejecutar", command=self._execute).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(file_row, text="Proponer mapping", command=self._suggest_mapping).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(file_row, text="Usar selección", command=self._confirm_selection).pack(
            side="left", padx=(8, 0)
        )
        ttk.Button(file_row, text="Abrir salida", command=self._open_output).pack(
            side="left", padx=(8, 0)
        )

        self.path_var = tk.StringVar(value="Ningún archivo cargado")
        self.kind_var = tk.StringVar(value="Tipo: —")
        self.output_var = tk.StringVar(
            value=f"Resultados: {Path('output').resolve()}  (el archivo original no se copia)"
        )
        ttk.Label(self, textvariable=self.path_var, wraplength=1000).pack(
            fill="x", padx=12
        )
        ttk.Label(self, textvariable=self.kind_var).pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(self, textvariable=self.output_var, wraplength=1000).pack(
            fill="x", padx=12, pady=(0, 4)
        )

        decision = ttk.LabelFrame(self, text="Decisión multiobjetivo / multicriterio / multimodal")
        decision.pack(fill="x", padx=12, pady=4)

        controls = ttk.Frame(decision)
        controls.pack(fill="x", padx=8, pady=6)
        ttk.Label(controls, text="Modalidad:").pack(side="left")
        self.modality_var = tk.StringVar(value=DecisionModality.NSGA_TOPSIS.value)
        self.modality_box = ttk.Combobox(
            controls,
            textvariable=self.modality_var,
            values=list(_MODALITY_LABELS.keys()),
            state="readonly",
            width=16,
        )
        self.modality_box.pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="Estrategia:").pack(side="left")
        self.strategy_var = tk.StringVar(value=ConversionStrategy.AUTO.value)
        self.strategy_box = ttk.Combobox(
            controls,
            textvariable=self.strategy_var,
            values=list(_STRATEGY_LABELS.keys()),
            state="readonly",
            width=16,
        )
        self.strategy_box.pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="Índice Pareto:").pack(side="left")
        self.pareto_index_var = tk.IntVar(value=0)
        ttk.Spinbox(
            controls,
            from_=0,
            to=99,
            textvariable=self.pareto_index_var,
            width=5,
        ).pack(side="left", padx=(4, 0))

        weights_frame = ttk.Frame(decision)
        weights_frame.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(weights_frame, text="Pesos TOPSIS:").pack(anchor="w")
        grid = ttk.Frame(weights_frame)
        grid.pack(fill="x")
        for column, name in enumerate(OBJECTIVE_NAMES):
            cell = ttk.Frame(grid)
            cell.grid(row=0, column=column, padx=4, sticky="ew")
            ttk.Label(cell, text=name.replace("_", "\n"), width=12).pack()
            var = tk.DoubleVar(value=float(DEFAULT_TOPSIS_WEIGHTS[name]))
            self._weight_vars[name] = var
            ttk.Scale(cell, from_=0.0, to=1.0, variable=var, orient="horizontal").pack(
                fill="x"
            )

        pareto_frame = ttk.Frame(decision)
        pareto_frame.pack(fill="x", padx=8, pady=(0, 8))
        columns = ("idx", "coverage", "compact", "connect", "buses", "lines")
        self.pareto_tree = ttk.Treeview(
            pareto_frame,
            columns=columns,
            show="headings",
            height=5,
            selectmode="browse",
        )
        headings = {
            "idx": "#",
            "coverage": "coverage",
            "compact": "compactness",
            "connect": "connectivity",
            "buses": "buses",
            "lines": "lines",
        }
        for key, title in headings.items():
            self.pareto_tree.heading(key, text=title)
            self.pareto_tree.column(key, width=90 if key != "idx" else 40, anchor="center")
        self.pareto_tree.pack(fill="x")
        self.pareto_tree.bind("<<TreeviewSelect>>", self._on_pareto_select)

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(self, textvariable=self.status_var).pack(fill="x", padx=12)

        ttk.Label(
            self,
            text="Registro de ejecución (scroll para ver todo el flujo):",
        ).pack(anchor="w", padx=12, pady=(8, 0))

        result = ttk.Frame(self)
        result.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.log = tk.Text(
            result,
            wrap="word",
            height=16,
            state="disabled",
            font=("Consolas", 10),
        )
        scroll = ttk.Scrollbar(result, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _current_weights(self) -> dict[str, float]:
        raw = {name: float(var.get()) for name, var in self._weight_vars.items()}
        try:
            return normalize_topsis_weights(raw)
        except ValueError:
            return dict(DEFAULT_TOPSIS_WEIGHTS)

    def _choose_file(self) -> None:
        if self._busy:
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="Seleccione el archivo a cargar",
            filetypes=_dialog_filetypes(),
        )
        if not selected:
            return
        self._apply_loaded(classify_file(Path(selected)))

    def _choose_files(self) -> None:
        if self._busy:
            return
        selected = filedialog.askopenfilenames(
            parent=self,
            title="Seleccione varios archivos (p. ej. RED, CARGA, equipo)",
            filetypes=(
                ("Texto CYMDIST / red", "*.txt"),
                ("CSV / TSV", "*.csv *.tsv"),
                (
                    "Formatos del conversor",
                    " ".join(f"*{suffix}" for suffix in sorted(programmed_file_suffixes())),
                ),
                ("Todos", "*.*"),
            ),
        )
        if not selected:
            return
        paths = tuple(Path(item) for item in selected)
        self._apply_loaded(classify_paths(paths))

    def _choose_folder(self) -> None:
        if self._busy:
            return
        selected = filedialog.askdirectory(
            parent=self,
            title="Seleccione la carpeta del proyecto o de los datos",
        )
        if not selected:
            return
        self._apply_loaded(classify_file(Path(selected)))

    def _apply_loaded(self, loaded: LoadedFile) -> None:
        self._loaded = loaded
        self._confirmed_mapping = None
        self._pareto = []
        self._refresh_pareto_tree()
        if loaded.members and len(loaded.members) > 1:
            names = ", ".join(path.name for path in loaded.members[:8])
            extra = "" if len(loaded.members) <= 8 else f" (+{len(loaded.members) - 8} más)"
            self.path_var.set(f"Paquete ({len(loaded.members)}): {names}{extra}")
        else:
            self.path_var.set(f"Ruta (no se copia): {loaded.path}")
        self.kind_var.set(f"Tipo: {loaded.label}")
        self.status_var.set("Detección lista. Proponga mapping o Ejecutar.")
        self._clear_log()
        self._append_log("=== Detección de entrada ===")
        self._append_log(loaded.detail)
        if loaded.detections:
            self._append_log(
                json.dumps(list(loaded.detections), indent=2, ensure_ascii=False)
            )
        self._append_log(f"Resultados se escribirán bajo: {Path('output').resolve()}")

    def _execute(self) -> None:
        if self._busy:
            return
        if self._loaded is None:
            messagebox.showinfo("GIS2DGS", "Primero cargue un archivo.", parent=self)
            self._choose_file()
            return
        if self._loaded.kind is LoadedFileKind.UNSUPPORTED:
            self._append_log(f"ERROR: {self._loaded.detail}")
            self.status_var.set("Entrada no soportada.")
            return
        self._busy = True
        self.status_var.set("Ejecutando… (vea el registro abajo)")
        self._append_log("")
        self._append_log("=== Ejecución integral ===")
        loaded = self._loaded
        modality = self.modality_var.get()
        strategy = self.strategy_var.get()
        weights = self._current_weights()
        pareto_index = int(self.pareto_index_var.get())
        confirmed = self._confirmed_mapping
        worker = threading.Thread(
            target=self._run_in_background,
            args=(loaded, modality, strategy, weights, pareto_index, confirmed),
            daemon=True,
        )
        worker.start()

    def _suggest_mapping(self) -> None:
        if self._busy:
            return
        if self._loaded is None:
            messagebox.showinfo("GIS2DGS", "Primero cargue un archivo.", parent=self)
            self._choose_file()
            return
        if self._loaded.kind is LoadedFileKind.UNSUPPORTED:
            self._append_log(f"ERROR: {self._loaded.detail}")
            return
        self._busy = True
        self.status_var.set("Proponiendo mapping…")
        self._append_log("")
        self._append_log("=== Propuesta de mapping ===")
        loaded = self._loaded
        output = Path("output") / "suggested_mapping.yaml"
        modality = self.modality_var.get()
        weights = self._current_weights()
        pareto_index = int(self.pareto_index_var.get())
        worker = threading.Thread(
            target=self._run_suggest_in_background,
            args=(loaded, output, modality, weights, pareto_index),
            daemon=True,
        )
        worker.start()

    def _confirm_selection(self) -> None:
        if not self._pareto:
            messagebox.showinfo(
                "GIS2DGS",
                "Primero pulse «Proponer mapping» para obtener el frente Pareto.",
                parent=self,
            )
            return
        index = int(self.pareto_index_var.get())
        if index < 0 or index >= len(self._pareto):
            messagebox.showerror("GIS2DGS", "Índice Pareto fuera de rango.", parent=self)
            return
        mapping = self._pareto[index].get("mapping")
        if not isinstance(mapping, dict):
            messagebox.showerror("GIS2DGS", "La alternativa no tiene mapping.", parent=self)
            return
        self._confirmed_mapping = mapping
        self.modality_var.set(DecisionModality.PARETO.value)
        self.status_var.set(f"Selección confirmada: Pareto #{index}")
        self._append_log(f"[Decisión] Mapping confirmado desde Pareto índice {index}.")
        summary = self._pareto[index].get("summary") or {}
        self._append_log(f"  buses={summary.get('buses')} lines={summary.get('lines')}")

    def _on_pareto_select(self, _event: object = None) -> None:
        selection = self.pareto_tree.selection()
        if not selection:
            return
        item = self.pareto_tree.item(selection[0])
        values = item.get("values") or ()
        if values:
            self.pareto_index_var.set(int(values[0]))

    def _refresh_pareto_tree(self) -> None:
        for item in self.pareto_tree.get_children():
            self.pareto_tree.delete(item)
        for index, entry in enumerate(self._pareto):
            objectives = entry.get("objectives") or {}
            summary = entry.get("summary") or {}
            self.pareto_tree.insert(
                "",
                "end",
                values=(
                    index,
                    f"{float(objectives.get('coverage', 0)):.2f}",
                    f"{float(objectives.get('compactness', 0)):.2f}",
                    f"{float(objectives.get('connectivity_readiness', 0)):.2f}",
                    summary.get("buses") or "—",
                    summary.get("lines") or "—",
                ),
            )

    def _progress_callback(self, message: str) -> None:
        self.after(0, lambda text=message: self._append_log(text))

    def _run_suggest_in_background(
        self,
        loaded: LoadedFile,
        output: Path,
        modality: str,
        weights: dict[str, float],
        pareto_index: int,
    ) -> None:
        outcome = suggest_mapping_for_loaded(
            loaded,
            output=output,
            on_progress=self._progress_callback,
            modality=modality,
            weights=weights,
            pareto_index=pareto_index if modality == DecisionModality.PARETO.value else None,
        )
        self.after(0, lambda: self._finish_suggest(outcome))

    def _run_in_background(
        self,
        loaded: LoadedFile,
        modality: str,
        strategy: str,
        weights: dict[str, float],
        pareto_index: int,
        confirmed: dict | None,
    ) -> None:
        outcome = load_and_run_loaded(
            loaded,
            on_progress=self._progress_callback,
            modality=modality,
            weights=weights,
            pareto_index=pareto_index if modality == DecisionModality.PARETO.value else None,
            strategy=strategy,
            confirmed_mapping=confirmed,
        )
        self.after(0, lambda: self._finish(outcome))

    def _finish_suggest(self, outcome: ExecutionOutcome) -> None:
        self._busy = False
        if outcome.success:
            pareto = outcome.payload.get("pareto") or []
            self._pareto = list(pareto) if isinstance(pareto, list) else []
            self._refresh_pareto_tree()
            selected = int(outcome.payload.get("selected_index") or 0)
            self.pareto_index_var.set(selected)
            self.status_var.set(
                f"Mapping propuesto. Pareto={len(self._pareto)} índice={selected}."
            )
            self._append_log(outcome.message)
            self._append_log(
                f"selected_objectives={outcome.payload.get('selected_objectives')}"
            )
        else:
            self.status_var.set("No se pudo proponer mapping.")
            self._append_log(outcome.message)

    def _finish(self, outcome: ExecutionOutcome) -> None:
        self._busy = False
        self._append_log("")
        if outcome.success:
            written = outcome.payload.get("written_to") or outcome.payload.get("output_dgs")
            conversion = outcome.payload.get("conversion")
            if not written and isinstance(conversion, dict):
                written = conversion.get("output_dgs")
            success_banner = "Ejecución completa y correcta"
            if written:
                self.output_var.set(f"{success_banner}. Resultado: {written}")
            else:
                self.output_var.set(f"{success_banner}.")
            self.status_var.set(success_banner)
            self._append_log("=== Resumen final ===")
            self._append_log(success_banner)
            self._append_log(outcome.message)
            decision = outcome.payload.get("decision")
            if isinstance(decision, dict):
                strategy = decision.get("conversion_strategy") or {}
                self._append_log(
                    "Decisión: "
                    f"modality={decision.get('modality')} "
                    f"strategy={strategy.get('strategy')} "
                    f"objectives={decision.get('selected_objectives')}"
                )
            if written:
                self._append_log(f"DGS: {written}")
        else:
            self.status_var.set("La ejecución no se completó.")
            self._append_log("=== Error / fin incompleto ===")
            self._append_log(outcome.message)
            brief = outcome.message.splitlines()[0] if outcome.message else "Error"
            if len(brief) > 180:
                brief = brief[:177] + "…"
            self.output_var.set(brief)
            conversion = outcome.payload.get("conversion")
            if isinstance(conversion, dict) and conversion.get("path"):
                self._append_log(f"Proyecto: {conversion['path']}")
            slim = {
                key: value
                for key, value in outcome.payload.items()
                if key not in {"schema", "mapping", "conversion"}
            }
            if isinstance(conversion, dict):
                slim["conversion"] = {
                    key: conversion[key]
                    for key in ("path", "output_dgs", "error")
                    if key in conversion
                } or {"path": conversion.get("path")}
            if slim:
                self._append_log(_format_payload(slim))

    def _open_output(self) -> None:
        target = Path("output")
        if self._loaded is not None and self._loaded.kind is LoadedFileKind.PROJECT:
            from gis2dgs.config import load_project_config

            try:
                target = load_project_config(self._loaded.path).output_dgs.parent
            except (OSError, ValueError):
                target = Path("output")
        target.mkdir(parents=True, exist_ok=True)
        _open_folder(target)

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        for line in text.splitlines() or [text]:
            if line:
                self.log.insert("end", f"[{self._timestamp()}] {line}\n")
            else:
                self.log.insert("end", "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()


def _open_folder(path: Path) -> None:
    startfile = getattr(os, "startfile", None)
    if startfile is not None:
        startfile(path)
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.run([opener, str(path)], check=False)


def _format_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def launch_gui(*, prompt_on_start: bool = False) -> None:
    app = ConverterApp(prompt_on_start=prompt_on_start)
    app.mainloop()
