from __future__ import annotations

import ast

from .context import (
    ImportNode,
    ModuleScanContext,
    _alias_binding_target_name,
    _all_assignment_export_names,
    _explicit_reexport_bindings,
    module_docstring_consumes_first_statement,
)


def middleman_candidate_metrics(context: ModuleScanContext) -> dict[str, int | list[str] | str] | None:
    if context.path.name == "__init__.py":
        return None

    import_nodes: list[ImportNode] = []
    alias_names: set[str] = set()
    exported_names: set[str] | None = None

    start_index = 1 if module_docstring_consumes_first_statement(context.tree) else 0
    imported_names = frozenset(_explicit_reexport_bindings(context.import_nodes))
    if not imported_names:
        return None

    for stmt in context.tree.body[start_index:]:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            if any(alias.name == "*" for alias in stmt.names):
                return None
            import_nodes.append(stmt)
            continue

        export_names = _all_assignment_export_names(stmt)
        if export_names is not None:
            exported_names = export_names
            continue

        alias_name = _alias_binding_target_name(stmt, imported_names)
        if alias_name is not None:
            alias_names.add(alias_name)
            continue

        return None

    if not import_nodes:
        return None

    first = import_nodes[0]
    last = import_nodes[-1]
    export_name_set = exported_names or (set(imported_names) | alias_names)
    if not export_name_set:
        return None

    return {
        "path": str(context.path),
        "import_lines": (last.end_lineno or last.lineno) - first.lineno + 1,
        "import_statements": len(import_nodes),
        "alias_bindings": len(alias_names),
        "exports": len(export_name_set),
        "exported_names": sorted(export_name_set),
    }