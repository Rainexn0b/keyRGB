from __future__ import annotations

from .context import (
    ModuleScanContext,
    _all_assignment_export_names,
    _explicit_reexport_bindings,
    module_docstring_consumes_first_statement,
)

_PURE_EXPORT_INIT_MAX_IMPORT_STATEMENTS = 3


def import_block_metrics(context: ModuleScanContext) -> tuple[int, int] | None:
    if not context.import_nodes:
        return None
    if _is_small_pure_export_init_facade(context):
        return None

    first = context.import_nodes[0]
    last = context.import_nodes[-1]
    return ((last.end_lineno or last.lineno) - first.lineno + 1, len(context.import_nodes))


def _is_small_pure_export_init_facade(context: ModuleScanContext) -> bool:
    if context.path.name != "__init__.py":
        return False
    if len(context.import_nodes) > _PURE_EXPORT_INIT_MAX_IMPORT_STATEMENTS:
        return False

    start_index = 1 if module_docstring_consumes_first_statement(context.tree) else 0
    remaining_body = context.tree.body[start_index + len(context.import_nodes) :]
    if len(remaining_body) != 1:
        return False

    export_names = _all_assignment_export_names(remaining_body[0])
    if export_names is None:
        return False

    imported_names = _explicit_reexport_bindings(context.import_nodes)
    return bool(imported_names) and export_names == imported_names