"""Phase 3 - Semantic analysis + symbol table (scopes, declarations, type checking)."""
from dataclasses import dataclass
from typing import List, Optional

from .ast_nodes import (Assign, Binary, Block, Call, ExprStmt, ForRange, FunctionDecl,
                        Identifier, If, Literal, Print, Return, Unary, VarDecl, While, show)
from .errors import CompileError

NUM = ("int", "float")
TN = {"int": "integer", "float": "float", "string": "string",
      "bool": "boolean", "void": "void", "error": "error"}

# JavaScript reserved words / names our generated code relies on.
RESERVED = {
    "var", "class", "new", "delete", "this", "null", "undefined", "function", "switch",
    "case", "default", "break", "continue", "do", "try", "catch", "finally", "throw",
    "typeof", "instanceof", "void", "with", "yield", "await", "async", "static",
    "enum", "export", "import", "super", "extends", "package", "interface", "private",
    "protected", "public", "implements", "of", "let", "NaN", "Infinity",
    "Math", "String", "console", "Object", "Number", "Array",
}
RESERVED -= {"let", "of"}          # 'let' is already a WebScript keyword; 'of' is harmless

CAT_DECL = "Variable declaration"
CAT_DUP = "Duplicate declarations"
CAT_TYPE = "Type compatibility"
CAT_FUNC = "Function declaration and usage"
CAT_ASSIGN = "Valid assignment operations"
CATEGORIES = [CAT_DECL, CAT_DUP, CAT_TYPE, CAT_FUNC, CAT_ASSIGN]


@dataclass
class Symbol:
    name: str
    type: str
    kind: str                       # variable | constant | parameter | function | loop variable
    scope: str
    line: int
    info: str = ""
    param_types: Optional[List[str]] = None

    def to_dict(self):
        return {"name": self.name, "type": TN[self.type], "kind": self.kind,
                "scope": self.scope, "line": self.line, "info": self.info}


class Scope:
    def __init__(self, name, parent=None):
        self.name, self.parent, self.table = name, parent, {}


def compatible(target, value):
    return target == value or (target == "float" and value == "int")


def always_returns(stmts):
    for s in stmts:
        if isinstance(s, Return):
            return True
        if isinstance(s, If) and s.else_body is not None \
                and always_returns(s.then_body) and always_returns(s.else_body):
            return True
    return False


class SemanticAnalyzer:
    def __init__(self):
        self.errors, self.symbols = [], []
        self.scope = None
        self.fn = None

    # ---- infrastructure ----
    def err(self, node, msg, cat):
        self.errors.append(CompileError("Semantic", msg, node.line, node.col, cat))

    def push(self, name):
        self.scope = Scope(name, self.scope)

    def pop(self):
        self.scope = self.scope.parent

    def lookup(self, name):
        s = self.scope
        while s:
            if name in s.table:
                return s.table[name]
            s = s.parent
        return None

    def declare(self, name, type_, kind, node, info=""):
        if name in RESERVED:
            self.err(node, f"'{name}' is reserved in the target language (JavaScript) and cannot be used as a name", CAT_DECL)
        prev = self.scope.table.get(name)
        if prev:
            self.err(node, f"Duplicate declaration of '{name}' (already declared on line {prev.line} in this scope)", CAT_DUP)
            return None
        sym = Symbol(name, type_, kind, self.scope.name, node.line, info)
        self.scope.table[name] = sym
        self.symbols.append(sym)
        return sym

    # ---- entry point ----
    def analyze(self, program):
        self.push("global")
        for node in program.body:                    # hoist function signatures
            if isinstance(node, FunctionDecl):
                ret = node.return_type or "void"
                sig = "(" + ", ".join(f"{p.name}: {TN[p.type_name]}" for p in node.params) + f") -> {TN[ret]}"
                sym = self.declare(node.name, ret, "function", node, sig)
                if sym:
                    sym.param_types = [p.type_name for p in node.params]
        for node in program.body:
            self.stmt(node)
        self.pop()
        self.errors.sort(key=lambda e: (e.line, e.col))
        return self.errors, self.symbols

    # ---- statements ----
    def stmt(self, s):
        getattr(self, "visit_" + type(s).__name__)(s)

    def body(self, stmts, scope_name):
        self.push(scope_name)
        for s in stmts:
            self.stmt(s)
        self.pop()

    def visit_FunctionDecl(self, node):
        self.push(f"function {node.name}")
        prev, self.fn = self.fn, node
        for i, p in enumerate(node.params, 1):
            self.declare(p.name, p.type_name, "parameter", p, f"parameter {i}")
        for s in node.body:
            self.stmt(s)
        if node.return_type and not always_returns(node.body):
            self.err(node, f"Function '{node.name}' must return a {TN[node.return_type]} value on every path", CAT_FUNC)
        self.fn = prev
        self.pop()

    def visit_VarDecl(self, node):
        t = self.operand(node.init)                  # evaluated BEFORE the name is declared
        vt = node.declared_type or t
        if node.declared_type and t != "error" and not compatible(node.declared_type, t):
            self.err(node, f"Cannot initialize {TN[node.declared_type]} variable '{node.name}' with a {TN[t]} value", CAT_TYPE)
        node.resolved_type = vt
        info = show(node.init)
        self.declare(node.name, vt, "constant" if node.is_const else "variable", node,
                     info if len(info) <= 40 else info[:37] + "...")

    def visit_Assign(self, node):
        sym = self.lookup(node.name)
        vt = self.operand(node.value)
        if sym is None:
            self.err(node, f"Assignment to undeclared variable '{node.name}'", CAT_DECL)
        elif sym.kind == "function":
            self.err(node, f"Cannot assign to function '{node.name}'", CAT_ASSIGN)
        elif sym.kind in ("constant", "loop variable"):
            self.err(node, f"Cannot assign to {sym.kind} '{node.name}'", CAT_ASSIGN)
        elif vt != "error" and sym.type != "error" and not compatible(sym.type, vt):
            self.err(node, f"Cannot assign a {TN[vt]} value to {TN[sym.type]} variable '{node.name}'.", CAT_ASSIGN)

    def condition(self, expr, what):
        t = self.operand(expr)
        if t not in ("bool", "error"):
            self.err(expr, f"Condition of '{what}' must be boolean, found {TN[t]}", CAT_TYPE)

    def visit_If(self, node):
        self.condition(node.cond, "if")
        self.body(node.then_body, f"if-block (line {node.line})")
        if node.else_body is not None:
            self.body(node.else_body, f"else-block (line {node.line})")

    def visit_While(self, node):
        self.condition(node.cond, "while")
        self.body(node.body, f"while-block (line {node.line})")

    def visit_ForRange(self, node):
        for e, what in ((node.start, "start"), (node.end, "end")):
            t = self.operand(e)
            if t not in ("int", "error"):
                self.err(e, f"range {what} must be an integer, found {TN[t]}", CAT_TYPE)
        self.push(f"for-block (line {node.line})")
        self.declare(node.var, "int", "loop variable", node, "range loop counter")
        for s in node.body:
            self.stmt(s)
        self.pop()

    def visit_Return(self, node):
        if self.fn is None:
            self.err(node, "'return' used outside of a function", CAT_FUNC)
            if node.value:
                self.operand(node.value)
            return
        ret = self.fn.return_type or "void"
        if node.value is None:
            if ret != "void":
                self.err(node, f"Function '{self.fn.name}' must return a {TN[ret]} value", CAT_FUNC)
            return
        t = self.operand(node.value)
        if ret == "void":
            self.err(node, f"Function '{self.fn.name}' is declared without a return type but returns a value", CAT_FUNC)
        elif t != "error" and not compatible(ret, t):
            self.err(node, f"Cannot return a {TN[t]} value from function '{self.fn.name}' declared to return {TN[ret]}", CAT_TYPE)

    def visit_Print(self, node):
        for a in node.args:
            self.operand(a)

    def visit_ExprStmt(self, node):
        self.expr(node.expr)

    # ---- expressions ----
    def operand(self, e):
        t = self.expr(e)
        if t == "void":
            self.err(e, "A function that returns no value cannot be used as a value", CAT_TYPE)
            e.type = "error"
            return "error"
        return t

    def expr(self, e):
        e.type = self._expr(e)
        return e.type

    def _expr(self, e):
        if isinstance(e, Literal):
            return e.type
        if isinstance(e, Identifier):
            sym = self.lookup(e.name)
            if sym is None:
                self.err(e, f"Use of undeclared variable '{e.name}'", CAT_DECL)
                return "error"
            if sym.kind == "function":
                self.err(e, f"'{e.name}' is a function; call it with ()", CAT_FUNC)
                return "error"
            return sym.type
        if isinstance(e, Unary):
            t = self.operand(e.operand)
            if t == "error":
                return "error"
            if (e.op == "-" and t in NUM) or (e.op == "!" and t == "bool"):
                return t
            self.err(e, f"Operator '{e.op}' cannot be applied to {TN[t]}", CAT_TYPE)
            return "error"
        if isinstance(e, Binary):
            return self.binary(e)
        if isinstance(e, Call):
            return self.call(e)
        raise AssertionError(f"unknown expression {e!r}")

    def binary(self, e):
        lt, rt = self.operand(e.left), self.operand(e.right)
        if "error" in (lt, rt):
            return "error"
        op, res = e.op, None
        both_num = lt in NUM and rt in NUM
        if op == "+":
            res = "string" if lt == rt == "string" else (
                ("float" if "float" in (lt, rt) else "int") if both_num else None)
        elif op in ("-", "*", "%"):
            res = ("float" if "float" in (lt, rt) else "int") if both_num else None
        elif op == "/":
            res = ("float" if "float" in (lt, rt) else "int") if both_num else None
        elif op in ("<", ">", "<=", ">="):
            res = "bool" if both_num or lt == rt == "string" else None
        elif op in ("==", "!="):
            res = "bool" if lt == rt or both_num else None
        elif op in ("&&", "||"):
            res = "bool" if lt == rt == "bool" else None
        if res is None:
            self.err(e, f"Operator '{op}' cannot be applied to {TN[lt]} and {TN[rt]}", CAT_TYPE)
            return "error"
        if op in ("/", "%") and isinstance(e.right, Literal) and e.right.type in NUM and e.right.value == 0:
            self.err(e, "Division by zero", CAT_TYPE)
            return "error"
        return res

    def call(self, e):
        types = [self.operand(a) for a in e.args]
        sym = self.lookup(e.name)
        if e.name == "str" and sym is None:                      # built-in
            if len(e.args) != 1:
                self.err(e, f"Built-in 'str' expects 1 argument but {len(e.args)} were given", CAT_FUNC)
            return "string"
        if sym is None:
            self.err(e, f"Call to undeclared function '{e.name}'", CAT_FUNC)
            return "error"
        if sym.kind != "function":
            self.err(e, f"'{e.name}' is not a function", CAT_FUNC)
            return "error"
        if len(e.args) != len(sym.param_types):
            self.err(e, f"Function '{e.name}' expects {len(sym.param_types)} argument(s) but {len(e.args)} were given", CAT_FUNC)
        else:
            for i, (want, got) in enumerate(zip(sym.param_types, types), 1):
                if got != "error" and not compatible(want, got):
                    self.err(e.args[i - 1], f"Argument {i} of '{e.name}' expects {TN[want]} but got {TN[got]}", CAT_FUNC)
        return sym.type
