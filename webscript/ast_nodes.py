"""AST node definitions plus helpers to print / walk the tree."""
import json
from dataclasses import dataclass, field, fields
from typing import Any, List, Optional


@dataclass
class Node:
    line: int = field(default=0, kw_only=True)
    col: int = field(default=0, kw_only=True)


@dataclass
class Expr(Node):
    type: Optional[str] = field(default=None, kw_only=True)   # filled by semantic analyzer


# ---- statements -----------------------------------------------------------
@dataclass
class Program(Node):
    body: List[Node]

@dataclass
class Param(Node):
    name: str
    type_name: str

@dataclass
class FunctionDecl(Node):
    name: str
    params: List[Param]
    return_type: Optional[str]
    body: List[Node]

@dataclass
class VarDecl(Node):
    name: str
    is_const: bool
    declared_type: Optional[str]
    init: Expr
    resolved_type: Optional[str] = field(default=None, kw_only=True)

@dataclass
class Assign(Node):
    name: str
    value: Expr

@dataclass
class If(Node):
    cond: Expr
    then_body: List[Node]
    else_body: Optional[List[Node]]

@dataclass
class While(Node):
    cond: Expr
    body: List[Node]

@dataclass
class ForRange(Node):
    var: str
    start: Expr
    end: Expr
    body: List[Node]

@dataclass
class Return(Node):
    value: Optional[Expr]

@dataclass
class Print(Node):
    args: List[Expr]

@dataclass
class ExprStmt(Node):
    expr: Expr

@dataclass
class Block(Node):          # only produced by the optimizer
    body: List[Node]

# ---- expressions ----------------------------------------------------------
@dataclass
class Literal(Expr):
    value: Any

@dataclass
class Identifier(Expr):
    name: str

@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass
class Unary(Expr):
    op: str
    operand: Expr

@dataclass
class Call(Expr):
    name: str
    args: List[Expr]


# ---- helpers --------------------------------------------------------------
def iter_nodes(node):
    yield node
    for f in fields(node):
        v = getattr(node, f.name)
        if isinstance(v, Node):
            yield from iter_nodes(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, Node):
                    yield from iter_nodes(x)


def has_call(node):
    return any(isinstance(n, Call) for n in iter_nodes(node))


def show(e):
    """WebScript-like text for an expression (used in logs, tables, IR)."""
    if isinstance(e, Literal):
        if e.type == "string":
            return json.dumps(e.value, ensure_ascii=False)
        if e.type == "bool":
            return "true" if e.value else "false"
        return repr(e.value)
    if isinstance(e, Identifier):
        return e.name
    if isinstance(e, Unary):
        return f"{e.op}{show(e.operand)}"
    if isinstance(e, Binary):
        def side(x):
            return f"({show(x)})" if isinstance(x, Binary) else show(x)
        return f"{side(e.left)} {e.op} {side(e.right)}"
    if isinstance(e, Call):
        return f"{e.name}({', '.join(show(a) for a in e.args)})"
    return "?"


_HIDDEN = {"line", "col", "type", "resolved_type"}


def _label(node):
    parts = []
    for f in fields(node):
        if f.name in _HIDDEN:
            continue
        v = getattr(node, f.name)
        if isinstance(v, (Node, list)) or v is None:
            continue
        parts.append(f"{f.name}={v!r}")
    s = type(node).__name__
    if parts:
        s += "(" + ", ".join(parts) + ")"
    t = getattr(node, "type", None)
    if t:
        s += f" : {t}"
    return s


def _children(node):
    out = []
    for f in fields(node):
        v = getattr(node, f.name)
        if isinstance(v, Node):
            out.append((f.name, v))
        elif isinstance(v, list):
            out += [(f"{f.name}[{i}]", x) for i, x in enumerate(v) if isinstance(x, Node)]
    return out


def tree_text(root):
    lines = [_label(root)]

    def walk(node, prefix):
        kids = _children(node)
        for i, (name, kid) in enumerate(kids):
            last = i == len(kids) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}: {_label(kid)}")
            walk(kid, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)
