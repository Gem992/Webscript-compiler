"""Phase 6 - JavaScript code generation (from the final, validated AST)."""
import json

from .ast_nodes import (Assign, Binary, Block, Call, ExprStmt, ForRange, FunctionDecl,
                        Identifier, If, Literal, Print, Return, Unary, VarDecl, While)

PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, ">": 4, "<=": 4, ">=": 4,
        "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}
JS_OP = {"==": "===", "!=": "!=="}


class JSGenerator:
    def __init__(self):
        self.lines = []
        self.depth = 0

    def emit(self, text):
        self.lines.append("    " * self.depth + text)

    # ---- expressions ----
    def expr(self, e, parent=0, right=False):
        if isinstance(e, Literal):
            if e.type == "string":
                return json.dumps(e.value, ensure_ascii=False)
            if e.type == "bool":
                return "true" if e.value else "false"
            return repr(e.value)
        if isinstance(e, Identifier):
            return e.name
        if isinstance(e, Unary):
            inner = self.expr(e.operand, 7)
            if e.op == "-" and inner.startswith("-"):
                inner = f"({inner})"
            return e.op + inner
        if isinstance(e, Call):
            args = ", ".join(self.expr(a) for a in e.args)
            return f"String({args})" if e.name == "str" else f"{e.name}({args})"
        if isinstance(e, Binary):
            p = PREC[e.op]
            l = self.expr(e.left, p)
            r = self.expr(e.right, p, right=True)
            if e.op == "/" and e.left.type == "int" and e.right.type == "int":
                return f"Math.trunc({l} / {r})"            # integer division
            s = f"{l} {JS_OP.get(e.op, e.op)} {r}"
            return f"({s})" if p < parent or (p == parent and right) else s
        raise AssertionError(e)

    # ---- statements ----
    def stmts(self, body):
        self.depth += 1
        for s in body:
            self.stmt(s)
        self.depth -= 1

    def stmt(self, s):
        if isinstance(s, VarDecl):
            self.emit(f"{'const' if s.is_const else 'let'} {s.name} = {self.expr(s.init)};")
        elif isinstance(s, Assign):
            self.emit(f"{s.name} = {self.expr(s.value)};")
        elif isinstance(s, Print):
            self.emit(f"console.log({', '.join(self.expr(a) for a in s.args)});")
        elif isinstance(s, ExprStmt):
            self.emit(self.expr(s.expr) + ";")
        elif isinstance(s, Return):
            self.emit("return;" if s.value is None else f"return {self.expr(s.value)};")
        elif isinstance(s, Block):
            self.emit("{")
            self.stmts(s.body)
            self.emit("}")
        elif isinstance(s, If):
            self.if_chain(s, "if")
        elif isinstance(s, While):
            self.emit(f"while ({self.expr(s.cond)}) {{")
            self.stmts(s.body)
            self.emit("}")
        elif isinstance(s, ForRange):
            self.emit(f"for (let {s.var} = {self.expr(s.start)}; {s.var} < {self.expr(s.end)}; {s.var}++) {{")
            self.stmts(s.body)
            self.emit("}")
        elif isinstance(s, FunctionDecl):
            self.emit(f"function {s.name}({', '.join(p.name for p in s.params)}) {{")
            self.stmts(s.body)
            self.emit("}")
        else:
            raise AssertionError(s)

    def if_chain(self, s, head):
        self.emit(f"{head} ({self.expr(s.cond)}) {{")
        self.stmts(s.then_body)
        if s.else_body and len(s.else_body) == 1 and isinstance(s.else_body[0], If):
            # "else if": print "} else if (...) {" by merging with the closing brace
            nested = s.else_body[0]
            self.if_chain_else(nested)
            return
        if s.else_body:
            self.emit("} else {")
            self.stmts(s.else_body)
        self.emit("}")

    def if_chain_else(self, nested):
        self.emit(f"}} else if ({self.expr(nested.cond)}) {{")
        self.stmts(nested.then_body)
        if nested.else_body and len(nested.else_body) == 1 and isinstance(nested.else_body[0], If):
            self.if_chain_else(nested.else_body[0])
            return
        if nested.else_body:
            self.emit("} else {")
            self.stmts(nested.else_body)
        self.emit("}")


def generate_js(program):
    g = JSGenerator()
    for s in program.body:
        g.stmt(s)
    return "\n".join(g.lines) + "\n"
