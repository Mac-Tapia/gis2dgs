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


class ConverterApp(tk.Tk):
    """Desktop window: load a source and run the integral flow."""

    def __init__(self, *, prompt_on_start: bool = True) -> None:
        super().__init__()
        self.title(f"GIS2DGS {__version__}")
        self.minsize(820, 560)
        self.geometry("960x640")
        self._loaded: LoadedFile | None = None
        self._busy = False
        self._build()
        if prompt_on_start:
            self.after(200, self._choose_file)

    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=8)
        ttk.Label(
            header,
            text="Cargue archivos y pulse Ejecutar",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=(
                "Puede cargar un archivo, varios TXT (red/cargas/equipo) o una carpeta. "
                "El registro muestra detección, paquete, inspección, mapping y conversión."
            ),
            wraplength=900,
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
        ttk.Button(file_row, text="Abrir salida", command=self._open_output).pack(
            side="left", padx=(8, 0)
        )

        self.path_var = tk.StringVar(value="Ningún archivo cargado")
        self.kind_var = tk.StringVar(value="Tipo: —")
        self.output_var = tk.StringVar(
            value=f"Resultados: {Path('output').resolve()}  (el archivo original no se copia)"
        )
        ttk.Label(self, textvariable=self.path_var, wraplength=920).pack(
            fill="x", padx=12
        )
        ttk.Label(self, textvariable=self.kind_var).pack(fill="x", padx=12, pady=(0, 4))
        ttk.Label(self, textvariable=self.output_var, wraplength=920).pack(
            fill="x", padx=12, pady=(0, 8)
        )

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
            height=22,
            state="disabled",
            font=("Consolas", 10),
        )
        scroll = ttk.Scrollbar(result, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

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
                ("Formatos del conversor", " ".join(
                    f"*{suffix}" for suffix in sorted(programmed_file_suffixes())
                )),
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
        if loaded.members and len(loaded.members) > 1:
            names = ", ".join(path.name for path in loaded.members[:8])
            extra = "" if len(loaded.members) <= 8 else f" (+{len(loaded.members) - 8} más)"
            self.path_var.set(
                f"Paquete ({len(loaded.members)}): {names}{extra}"
            )
        else:
            self.path_var.set(f"Ruta (no se copia): {loaded.path}")
        self.kind_var.set(f"Tipo: {loaded.label}")
        self.status_var.set("Detección lista. Pulse Ejecutar.")
        self._clear_log()
        self._append_log("=== Detección de entrada ===")
        self._append_log(loaded.detail)
        if loaded.detections:
            self._append_log(
                json.dumps(list(loaded.detections), indent=2, ensure_ascii=False)
            )
        self._append_log(
            f"Resultados se escribirán bajo: {Path('output').resolve()}"
        )

    def _execute(self) -> None:
        if self._busy:
            return
        if self._loaded is None:
            messagebox.showinfo(
                "GIS2DGS",
                "Primero cargue un archivo.",
                parent=self,
            )
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
        worker = threading.Thread(
            target=self._run_in_background,
            args=(loaded,),
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
        worker = threading.Thread(
            target=self._run_suggest_in_background,
            args=(loaded, output),
            daemon=True,
        )
        worker.start()

    def _progress_callback(self, message: str) -> None:
        self.after(0, lambda text=message: self._append_log(text))

    def _run_suggest_in_background(self, loaded: LoadedFile, output: Path) -> None:
        outcome = suggest_mapping_for_loaded(
            loaded,
            output=output,
            on_progress=self._progress_callback,
        )
        self.after(0, lambda: self._finish(outcome))

    def _run_in_background(self, loaded: LoadedFile) -> None:
        outcome = load_and_run_loaded(loaded, on_progress=self._progress_callback)
        self.after(0, lambda: self._finish(outcome))

    def _finish(self, outcome: ExecutionOutcome) -> None:
        self._busy = False
        self._append_log("")
        if outcome.success:
            written = outcome.payload.get("written_to") or outcome.payload.get("output_dgs")
            conversion = outcome.payload.get("conversion")
            if not written and isinstance(conversion, dict):
                written = conversion.get("output_dgs")
            if written:
                self.output_var.set(f"Resultado guardado en: {written}")
            self.status_var.set("Ejecución correcta.")
            self._append_log("=== Resumen final ===")
            self._append_log(outcome.message)
            self._append_log(_format_payload(outcome.payload))
        else:
            self.status_var.set("La ejecución no se completó.")
            self._append_log("=== Error / fin incompleto ===")
            self._append_log(outcome.message)
            if outcome.payload:
                self._append_log(_format_payload(outcome.payload))

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


def launch_gui(*, prompt_on_start: bool = True) -> None:
    app = ConverterApp(prompt_on_start=prompt_on_start)
    app.mainloop()
