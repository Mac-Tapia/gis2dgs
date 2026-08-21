from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from ..compact import compact_frame, sample_select_sql
from ..dataset import InputDataset
from ..exceptions import InputError


class SqlAlchemyInputReader:
    """Generic database reader using SQLAlchemy dialect/driver URLs.

    Database-specific drivers remain optional. This keeps the core converter
    independent from PostgreSQL, SQL Server, Oracle, SQLite or other engines.
    """

    def __init__(
        self,
        uri: str | Path,
        *,
        source_id: str | None = None,
        tables: tuple[str, ...] | None = None,
        queries: dict[str, str] | None = None,
        spatial_queries: dict[str, str] | None = None,
        geometry_column: str = "geometry",
        aliases: dict[str, str] | None = None,
        connect_args: dict[str, Any] | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
    ) -> None:
        self.uri = self._normalize_uri(uri)
        self.source_id = source_id
        self.tables = tables
        self.queries = dict(queries or {})
        self.spatial_queries = dict(spatial_queries or {})
        self.geometry_column = geometry_column
        self.aliases = dict(aliases or {})
        self.connect_args = dict(connect_args or {})
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame

    @staticmethod
    def _normalize_uri(uri: str | Path) -> str:
        text = str(uri)
        path = Path(text)
        if "://" in text:
            if text.startswith("mssql"):
                from gis2dgs.input.readers.mssql_backup import sanitize_odbc_url

                return sanitize_odbc_url(text)
            return text
        if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            return f"sqlite:///{path.resolve()}"
        from ..detector import is_sqlite_file

        if path.is_file() and is_sqlite_file(path):
            return f"sqlite:///{path.resolve()}"
        return text

    def _resolved_uri(self) -> str:
        if not self.uri.startswith("mssql"):
            return self.uri
        from gis2dgs.input.mssql_ensure import resolve_runtime_mssql_url

        self.uri = resolve_runtime_mssql_url(self.uri)
        return self.uri

    def _engine(self) -> Engine:
        try:
            return create_engine(self._resolved_uri(), connect_args=self.connect_args)
        except Exception as exc:
            raise InputError(f"Unable to create database engine: {exc}") from exc

    def read(self) -> InputDataset:
        try:
            return self._read_with_engine()
        except Exception as exc:
            if self.uri.startswith("mssql") and self._mssql_should_refresh(exc):
                return self._read_after_mssql_refresh(exc)
            if isinstance(exc, InputError):
                raise
            raise InputError(f"Unable to read database source: {exc}") from exc

    @staticmethod
    def _mssql_should_refresh(exc: BaseException) -> bool:
        from gis2dgs.input.readers.mssql_backup import connection_needs_sql_reconnect

        return connection_needs_sql_reconnect(exc)

    def _read_after_mssql_refresh(self, original: BaseException) -> InputDataset:
        from gis2dgs.input.mssql_ensure import (
            ensure_sql_server,
            resolve_runtime_mssql_url,
        )

        try:
            ensure_sql_server()
            self.uri = resolve_runtime_mssql_url(self.uri)
            return self._read_with_engine()
        except InputError:
            raise
        except Exception as exc:
            raise InputError(
                "SQL Server rechazó el usuario sa o la cadena ODBC. "
                "Ejecute scripts/ensure_mssql.ps1 y vuelva a cargar el archivo. "
                f"Detalle: {exc}"
            ) from original

    def _read_with_engine(self) -> InputDataset:
        engine = self._engine()
        result = InputDataset()
        try:
            inspector = inspect(engine)
            available_tables = tuple(inspector.get_table_names())
            requested = self.tables
            if requested is None and not self.queries and not self.spatial_queries:
                requested = available_tables
            for table in requested or ():
                if table not in available_tables:
                    raise InputError(f"Database table not found: {table}")
                if self.sample_rows is not None and self.sample_rows > 0:
                    frame = pd.read_sql_query(
                        sample_select_sql(engine, table, self.sample_rows), engine
                    )
                else:
                    frame = pd.read_sql_table(table, engine)
                logical = self.aliases.get(table, table)
                self._add(result, logical, frame, {"format": "database", "table": table})
            for logical, sql in self.queries.items():
                frame = pd.read_sql_query(sql, engine)
                if self.sample_rows is not None and self.sample_rows > 0:
                    frame = frame.iloc[: int(self.sample_rows)]
                self._add(
                    result,
                    self.aliases.get(logical, logical),
                    frame,
                    {"format": "database", "query": logical},
                )
            for logical, sql in self.spatial_queries.items():
                frame = gpd.read_postgis(sql, engine, geom_col=self.geometry_column)
                if self.sample_rows is not None and self.sample_rows > 0:
                    frame = frame.iloc[: int(self.sample_rows)]
                self._add(
                    result,
                    self.aliases.get(logical, logical),
                    frame,
                    {
                        "format": "database",
                        "query": logical,
                        "spatial": True,
                        "geometry_column": self.geometry_column,
                        "crs": str(frame.crs) if frame.crs is not None else None,
                    },
                )
        except InputError:
            raise
        except Exception as exc:
            raise InputError(f"Unable to read database source: {exc}") from exc
        finally:
            engine.dispose()
        return result

    def _add(
        self,
        result: InputDataset,
        name: str,
        frame: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> None:
        stored = compact_frame(frame, copy=False) if self.compact else frame
        result.add_table(
            name,
            stored,
            source_id=self.source_id,
            metadata=metadata,
            copy_frame=self.copy_frame,
        )
