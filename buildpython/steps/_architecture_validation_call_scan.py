from __future__ import annotations

import ast

from ._architecture_validation_helpers import (
    _NON_LITERAL,
    _dotted_name,
    _literal_value,
    _ScannedCall,
)


def _scan_python_calls(text: str) -> tuple[_ScannedCall, ...]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()

    scanned_calls: list[_ScannedCall] = []

    class _CallVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self._lexical_locks: list[str] = []
            self._bindings: list[dict[str, str | None]] = [{}]

        def _lookup_binding(self, name: str) -> str | None:
            for scope in reversed(self._bindings):
                if name in scope:
                    return scope[name]
            return None

        def _bind_name(self, name: str, canonical: str | None = None) -> None:
            self._bindings[-1][name] = canonical

        def _bind_target(self, target: ast.AST, canonical: str | None = None) -> None:
            if isinstance(target, (ast.List, ast.Tuple)):
                for element in target.elts:
                    self._bind_target(element, canonical)
                return
            if isinstance(target, ast.Starred):
                self._bind_target(target.value, canonical)
                return
            if isinstance(target, ast.Name):
                self._bind_name(target.id, canonical)

        def _canonical_dotted_name(self, dotted_name: str) -> str:
            parts = dotted_name.split(".")
            canonical_root = self._lookup_binding(parts[0])
            if canonical_root is None:
                return dotted_name
            return ".".join((canonical_root, *parts[1:]))

        def _canonical_call(self, node: ast.Call) -> tuple[str, str] | None:
            if isinstance(node.func, ast.Name):
                canonical = self._lookup_binding(node.func.id)
                if canonical is None:
                    return None
                receiver, separator, method = canonical.rpartition(".")
                if not separator:
                    return None
                return receiver, method

            if not isinstance(node.func, ast.Attribute):
                return None
            receiver_name = _dotted_name(node.func.value)
            if receiver_name is None:
                return None
            return self._canonical_dotted_name(receiver_name), node.func.attr

        def visit_Call(self, node: ast.Call) -> None:
            canonical_call = self._canonical_call(node)
            if canonical_call is not None:
                receiver, method = canonical_call
                scanned_calls.append(
                    _ScannedCall(
                        receiver=receiver,
                        method=method,
                        line=int(getattr(node, "lineno", 0)),
                        lexical_locks=tuple(self._lexical_locks),
                        literal_keywords=tuple(
                            (keyword.arg, value)
                            for keyword in node.keywords
                            if keyword.arg is not None and (value := _literal_value(keyword.value)) is not _NON_LITERAL
                        ),
                    )
                )
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                canonical = alias.name if alias.asname else bound_name
                self._bind_name(bound_name, canonical)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            if int(getattr(node, "level", 0)) != 0:
                return
            module = str(getattr(node, "module", "") or "").strip()
            if not module:
                return
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound_name = alias.asname or alias.name
                self._bind_name(bound_name, f"{module}.{alias.name}")

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            for target in node.targets:
                self._bind_target(target)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self.visit(node.value)
            self._bind_target(node.target)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self.visit(node.value)
            self._bind_target(node.target)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            self.visit(node.value)
            self._bind_target(node.target)

        def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
            self.visit(node.iter)
            self._bind_target(node.target)
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            self.visit_For(node)

        def visit_With(self, node: ast.With) -> None:
            self._visit_with(node)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            self._visit_with(node)

        def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
            lock_count = 0
            for item in node.items:
                self.visit(item.context_expr)
                context_name = _dotted_name(item.context_expr)
                if context_name is not None:
                    self._lexical_locks.append(context_name)
                    lock_count += 1
                if item.optional_vars is not None:
                    self.visit(item.optional_vars)
                    self._bind_target(item.optional_vars)
            for statement in node.body:
                self.visit(statement)
            if lock_count:
                del self._lexical_locks[-lock_count:]

        def _visit_nested_scope(self, node: ast.AST) -> None:
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            self.generic_visit(node)
            self._lexical_locks = saved_locks

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._visit_function_definition(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._visit_function_definition(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            self._bindings.append({})
            self._bind_function_arguments(node.args)
            self.visit(node.body)
            self._bindings.pop()
            self._lexical_locks = saved_locks

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self._bind_name(node.name)
            for decorator in node.decorator_list:
                self.visit(decorator)
            for base in node.bases:
                self.visit(base)
            for keyword in node.keywords:
                self.visit(keyword.value)
            self._bindings.append({})
            for statement in node.body:
                self.visit(statement)
            self._bindings.pop()

        def _visit_function_definition(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self._bind_name(node.name)
            for decorator in node.decorator_list:
                self.visit(decorator)
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is not None:
                    self.visit(default)
            saved_locks = self._lexical_locks
            self._lexical_locks = []
            self._bindings.append({})
            self._bind_function_arguments(node.args)
            for statement in node.body:
                self.visit(statement)
            self._bindings.pop()
            self._lexical_locks = saved_locks

        def _bind_function_arguments(self, arguments: ast.arguments) -> None:
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            ):
                self._bind_name(argument.arg)
            if arguments.vararg is not None:
                self._bind_name(arguments.vararg.arg)
            if arguments.kwarg is not None:
                self._bind_name(arguments.kwarg.arg)

    _CallVisitor().visit(tree)
    scanned_calls.sort(key=lambda item: (item.line, item.receiver, item.method))
    return tuple(scanned_calls)
