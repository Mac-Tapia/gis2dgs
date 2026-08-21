from __future__ import annotations

from gis2dgs.powerfactory import PowerFactoryModel, PowerFactoryObject

from .exceptions import DgsMappingError, DgsSchemaNotConfiguredError
from .models import DgsDocument, DgsObject, DgsRow, DgsTable
from .schema import DgsClassMapping, DgsSchema, UnmappedPolicy
from .validation import validate_dgs_document


class DgsMapper:
    """Map the Phase 7 semantic PowerFactory model to exact configured DGS tables."""

    def __init__(self, schema: DgsSchema | None = None) -> None:
        self.schema = schema

    def map_powerfactory_model(self, model: PowerFactoryModel) -> DgsDocument:
        schema = self._require_schema()
        document = DgsDocument()

        # Create configured tables up front so empty but required sheets are known.
        table_columns: dict[str, list[str]] = {}
        for mapping in schema.classes.values():
            columns = table_columns.setdefault(mapping.table, [])
            for column in mapping.all_columns():
                if column not in columns:
                    columns.append(column)
        for table_name, columns in table_columns.items():
            document.add_table(DgsTable(table_name, tuple(columns)))

        for obj in model.objects.values():
            class_mapping = schema.mapping_for(obj.class_name)
            if class_mapping is None:
                if schema.unmapped_class_policy == UnmappedPolicy.SKIP:
                    continue
                raise DgsMappingError(
                    f"No DGS class mapping configured for PowerFactory class {obj.class_name!r}."
                )
            row = self._map_object(obj, class_mapping, schema)
            document.get_table(class_mapping.table).add(row)

        report = validate_dgs_document(document, schema)
        if not report.is_valid:
            raise DgsMappingError(report.errors[0].message)
        return document

    def map_network(self, network: object) -> DgsDocument:
        del network
        raise DgsSchemaNotConfiguredError(
            "Phase 8 accepts PowerFactoryModel. Map NetworkModel with PowerFactoryMapper first."
        )

    def _require_schema(self) -> DgsSchema:
        if self.schema is None:
            raise DgsSchemaNotConfiguredError(
                "DGS mapper requires a configured DGS schema."
            )
        self.schema.require_configured()
        return self.schema

    def _map_object(
        self,
        obj: PowerFactoryObject,
        mapping: DgsClassMapping,
        schema: DgsSchema,
    ) -> DgsRow:
        values: dict[str, object] = dict(mapping.static_values)
        values[mapping.identity.foreign_key_column] = obj.foreign_key
        values[mapping.identity.name_column] = obj.name
        if mapping.identity.parent_column is not None:
            values[mapping.identity.parent_column] = (
                obj.parent.target_key if obj.parent is not None else None
            )

        unmapped_attributes = set(obj.attributes).difference(mapping.attributes)
        if schema.strict_unmapped_attributes and unmapped_attributes:
            raise DgsMappingError(
                f"PowerFactory object {obj.foreign_key!r} ({obj.class_name}) has unmapped "
                f"semantic attributes: {sorted(unmapped_attributes)}"
            )
        for semantic_name, field_mapping in mapping.attributes.items():
            if semantic_name in obj.attributes:
                values[field_mapping.column] = field_mapping.transform(
                    obj.attributes[semantic_name]
                )

        unmapped_references = set(obj.references).difference(mapping.references)
        if schema.strict_unmapped_references and unmapped_references:
            raise DgsMappingError(
                f"PowerFactory object {obj.foreign_key!r} ({obj.class_name}) has unmapped "
                f"semantic references: {sorted(unmapped_references)}"
            )
        for semantic_name, reference_mapping in mapping.references.items():
            reference = obj.references.get(semantic_name)
            if reference is not None:
                values[reference_mapping.column] = reference_mapping.transform(
                    reference.target_key
                )

        return DgsRow(object_key=obj.foreign_key, values=values)


__all__ = ["DgsMapper", "DgsObject"]
