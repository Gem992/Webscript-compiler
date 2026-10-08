"""Phase 4 - Intermediate representation: AST -> three-address code (list of text lines)."""
from .ast_nodes import (Assign, Binary, Block, Call, ExprStmt, ForRange, FunctionDecl,
                        Identifier, If, Literal, Print, Return, Unary, VarDecl, While, show)


class IRGenerator:
    def __init__(self):
        self.lines = []
        self.t = 0
        self.l = 0

    def temp(self):
        self.t += 1
        return f"t{self.t}"

    def label(self):
        self.l += 1
        return f"L{self.l}"

    def emit(self, text):
        self.lines.append("    " + text)

    def place(self, label):
        self.lines.append(f"{label}:")

    # ---- expressions: return the operand holding the value ----
    def expr(self, e):
        if isinstance(e, (Literal, Identifier)):
            return show(e)
        if isinstance(e, Unary):
            o = self.expr(e.operand)
            t = self.temp()
            self.emit(f"{t} = {e.op}({o})" if o.startswith("-") else f"{t} = {e.op}{o}")
            return t
        if isinstance(e, Binary):
            l, r = self.expr(e.left), self.expr(e.right)
            t = self.temp()
            self.emit(f"{t} = {l} {e.op} {r}")
            return t
        if isinstance(e, Call):
            return self.call(e, want_value=True)
        raise AssertionError(e)

    def call(self, e, want_value):
        args = [self.expr(a) for a in e.args]
        for a in args:
            self.emit(f"param {a}")
        if want_value:
            t = self.temp()
            self.emit(f"{t} = call {e.name}, {len(args)}")
            return t
        self.emit(f"call {e.name}, {len(args)}")

    # ---- statements ----
    def stmts(self, body):
        for s in body:
            self.stmt(s)

    def stmt(self, s):
        if isinstance(s, (VarDecl,)):
            self.emit(f"{s.name} = {self.expr(s.init)}")
        elif isinstance(s, Assign):
            self.emit(f"{s.name} = {self.expr(s.value)}")
        elif isinstance(s, Print):
            self.emit("print " + ", ".join(self.expr(a) for a in s.args))
        elif isinstance(s, ExprStmt):
            self.call(s.expr, want_value=False)
        elif isinstance(s, Return):
            self.emit("return" if s.value is None else f"return {self.expr(s.value)}")
        elif isinstance(s, Block):
            self.stmts(s.body)
        elif isinstance(s, If):
            c = self.expr(s.cond)
            end = self.label()
            if s.else_body:
                els = self.label()
                self.emit(f"ifFalse {c} goto {els}")
                self.stmts(s.then_body)
                self.emit(f"goto {end}")
                self.place(els)
                self.stmts(s.else_body)
            else:
                self.emit(f"ifFalse {c} goto {end}")
                self.stmts(s.then_body)
            self.place(end)
        elif isinstance(s, While):
            top, end = self.label(), self.label()
            self.place(top)
            c = self.expr(s.cond)
            self.emit(f"ifFalse {c} goto {end}")
            self.stmts(s.body)
            self.emit(f"goto {top}")
            self.place(end)
        elif isinstance(s, ForRange):
            top, end = self.label(), self.label()
            self.emit(f"{s.var} = {self.expr(s.start)}")
            self.place(top)
            limit = self.expr(s.end)
            t = self.temp()
            self.emit(f"{t} = {s.var} < {limit}")
            self.emit(f"ifFalse {t} goto {end}")
            self.stmts(s.body)
            self.emit(f"{s.var} = {s.var} + 1")
            self.emit(f"goto {top}")
            self.place(end)
        elif isinstance(s, FunctionDecl):
            self.place(f"func {s.name}({', '.join(p.name for p in s.params)})")
            self.stmts(s.body)
            self.lines.append("endfunc")
        else:
            raise AssertionError(s)


def generate_ir(program):
    g = IRGenerator()
    g.stmts(program.body)
    return g.lines
