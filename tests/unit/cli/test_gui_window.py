from pathlib import Path
from tkinter import TclError

import pytest

from gis2dgs.cli.gui import ConverterApp
from gis2dgs.cli.workspace import ExecutionOutcome, LoadedFile, LoadedFileKind


def test_converter_window_shows_execution_result() -> None:
    try:
        app = ConverterApp(prompt_on_start=False)
    except TclError:
        pytest.skip("Tkinter display is not available")
    try:
        app.update_idletasks()
        app._loaded = LoadedFile(
            Path("demo.yaml"),
            LoadedFileKind.PROJECT,
            "Proyecto: demo",
            "detalle",
        )
        app._finish(
            ExecutionOutcome(
                True,
                "convert",
                "Conversión completada.",
                {"buses": 2, "written_to": "output/demo/red_dgs.xlsx"},
            )
        )
        app.update_idletasks()
        log_text = app.log.get("1.0", "end")
        assert "Ejecución completa y correcta" in log_text
        assert "Conversión completada." in log_text
        assert "Resumen final" in log_text
        assert app.status_var.get() == "Ejecución completa y correcta"
        assert "Ejecución completa y correcta" in app.output_var.get()
        assert "red_dgs.xlsx" in app.output_var.get()
    finally:
        app.destroy()


def test_converter_window_shows_failure_status() -> None:
    try:
        app = ConverterApp(prompt_on_start=False)
    except TclError:
        pytest.skip("Tkinter display is not available")
    try:
        app._finish(
            ExecutionOutcome(
                False,
                "convert",
                "Inspección y mapping listos, pero la conversión falló: boom",
                {},
            )
        )
        app.update_idletasks()
        assert app.status_var.get() == "La ejecución no se completó."
        assert "conversión falló" in app.log.get("1.0", "end")
        assert "conversión falló" in app.output_var.get()
    finally:
        app.destroy()


def test_converter_window_apply_loaded_shows_package_names() -> None:
    try:
        app = ConverterApp(prompt_on_start=False)
    except TclError:
        pytest.skip("Tkinter display is not available")
    try:
        members = (
            Path("RED_030826.txt"),
            Path("CARGA_030826.txt"),
            Path("BD_Equipo_V26.txt"),
        )
        app._apply_loaded(
            LoadedFile(
                Path("paquete"),
                LoadedFileKind.INPUT,
                "Paquete: 3 archivo(s)",
                "Análisis de paquete",
                members=members,
            )
        )
        assert "Paquete (3)" in app.path_var.get()
        assert "RED_030826.txt" in app.path_var.get()
        assert app.kind_var.get() == "Tipo: Paquete: 3 archivo(s)"
    finally:
        app.destroy()
