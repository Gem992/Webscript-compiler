"""Phase 5 - Optimization (works on the AST, repeated until nothing changes).

  * constant folding             10 + 20          -> 30
  * algebraic simplification     x * 1, x + 0 ... -> x
  * constant propagation         const N = 5      -> uses of N become 5
  * dead-code elimination        if false {..}, code after return, unused consts
"""
import copy
import math

from .ast_nodes import (Assign, Binary, Block, Call, ExprStmt, ForRange, FunctionDecl,
                        Identifier, If, Literal, Print, Program, Return, Unary, VarDecl,
                        While, has_call, iter_nodes, show)

NUM = ("int", "float")


def trunc_div(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def lit(value, like):
    if isinstance(value, bool):
        t = "bool"
    elif isinstance(value, int):
        t = "int"
    elif isinstance(value, float):
        t = "float"
    else:
        t = "string"
    return Literal(value, type=t, line=like.line, col=like.col)


def fold(op, l, r):
    """Fold a binary operation on two literals. Returns a Python value or None."""
    a, b = l.value, r.value
    both_num = l.type in NUM and r.type in NUM
    if op == "+" and l.type == r.type == "string":
        return a + b
    if both_num and op in ("+", "-", "*", "/", "%"):
        both_int = l.type == r.type == "int"
        if op == "+":
            v = a + b
        elif op == "-":
            v = a - b
        elif op == "*":
            v = a * b
        else:
            if b == 0:
                return None
            if op == "/":
                v = trunc_div(a, b) if both_int else a / b
            else:
                v = a - b * trunc_div(a, b) if both_int else math.fmod(a, b)
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v
    if op in ("<", ">", "<=", ">=") and (both_num or l.type == r.type == "string"):
        return {"<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
    if op in ("==", "!=") and (both_num or l.type == r.type):
        return (a == b) if op == "==" else (a != b)
    if op in ("&&", "||") and l.type == r.type == "bool":
        return (a and b) if op == "&&" else (a or b)
    return None


class Optimizer:
    def __init__(self):
        self.log = []
        self.scopes = []

    def note(self, node, kind, text):
        self.log.append(f"Line {node.line}: {kind}: {text}")

    # ---- driver ----
    def run(self, program):
        prog = copy.deepcopy(program)
        for _ in range(6):
            before = len(self.log)
            self.scopes = [{}]
            prog.body = self.stmts(prog.body, new_scope=False)
            self.remove_unused_consts(prog)
            if len(self.log) == before:
                break
        return prog

    def lookup(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return sc[name]
        return None

    # ---- statements ----
    def stmts(self, body, init=None, new_scope=True):
        if new_scope:
            self.scopes.append(dict(init or {}))
        out = []
        for i, s in enumerate(body):
            out.extend(self.stmt(s))
            if isinstance(s, Return):
                if i + 1 < len(body):
                    self.note(body[i + 1], "dead-code elimination",
                              f"removed {len(body) - i - 1} unreachable statement(s) after return")
                break
        if new_scope:
            self.scopes.pop()
        return out

    @staticmethod
    def inline(body):
        if any(isinstance(x, (VarDecl, FunctionDecl)) for x in body):
            return [Block(body)]
        return body

    def stmt(self, s):
        if isinstance(s, VarDecl):
            s.init = self.expr(s.init)
            value = None
            if s.is_const and isinstance(s.init, Literal):
                value = s.init
                if s.resolved_type == "float" and value.type == "int":
                    value = Literal(float(value.value), type="float")
            self.scopes[-1][s.name] = value
            return [s]
        if isinstance(s, Assign):
            s.value = self.expr(s.value)
            return [s]
        if isinstance(s, Print):
            s.args = [self.expr(a) for a in s.args]
            return [s]
        if isinstance(s, ExprStmt):
            s.expr = self.expr(s.expr)
            return [s]
        if isinstance(s, Return):
            if s.value is not None:
                s.value = self.expr(s.value)
            return [s]
        if isinstance(s, Block):
            return self.inline(self.stmts(s.body))
        if isinstance(s, If):
            s.cond = self.expr(s.cond)
            s.then_body = self.stmts(s.then_body)
            s.else_body = self.stmts(s.else_body) if s.else_body is not None else None
            if not s.else_body:
                s.else_body = None
            if isinstance(s.cond, Literal):
                taken = "then" if s.cond.value else "else"
                self.note(s, "dead-code elimination",
                          f"condition is always {show(s.cond)}; kept only the {taken}-branch")
                return self.inline(s.then_body if s.cond.value else (s.else_body or []))
            return [s]
        if isinstance(s, While):
            s.cond = self.expr(s.cond)
            if isinstance(s.cond, Literal) and s.cond.value is False:
                self.note(s, "dead-code elimination", "removed while-loop whose condition is always false")
                return []
            s.body = self.stmts(s.body)
            return [s]
        if isinstance(s, ForRange):
            s.start, s.end = self.expr(s.start), self.expr(s.end)
            if isinstance(s.start, Literal) and isinstance(s.end, Literal) and s.start.value >= s.end.value:
                self.note(s, "dead-code elimination", "removed for-loop with an empty range")
                return []
            s.body = self.stmts(s.body, {s.var: None})
            return [s]
        if isinstance(s, FunctionDecl):
            s.body = self.stmts(s.body, {p.name: None for p in s.params})
            return [s]
        raise AssertionError(s)

    # ---- expressions ----
    def expr(self, e):
        if isinstance(e, Identifier):
            value = self.lookup(e.name)
            if value is not None:
                self.note(e, "constant propagation", f"'{e.name}' → {show(value)}")
                return Literal(value.value, type=value.type, line=e.line, col=e.col)
            return e
        if isinstance(e, Literal):
            return e
        if isinstance(e, Call):
            e.args = [self.expr(a) for a in e.args]
            return e
        if isinstance(e, Unary):
            e.operand = self.expr(e.operand)
            o = e.operand
            if isinstance(o, Literal):
                if e.op == "-" and o.type in NUM:
                    return self.folded(e, Literal(-o.value, type=o.type, line=e.line, col=e.col))
                if e.op == "!" and o.type == "bool":
                    return self.folded(e, Literal(not o.value, type="bool", line=e.line, col=e.col))
            return e
        if isinstance(e, Binary):
            e.left, e.right = self.expr(e.left), self.expr(e.right)
            if isinstance(e.left, Literal) and isinstance(e.right, Literal):
                v = fold(e.op, e.left, e.right)
                if v is not None:
                    return self.folded(e, lit(v, e))
            return self.algebraic(e)
        raise AssertionError(e)

    def folded(self, old, new):
        self.note(old, "constant folding", f"{show(old)} → {show(new)}")
        return new

    def algebraic(self, e):
        op, l, r = e.op, e.left, e.right

        def is_lit(x, value, types):
            return isinstance(x, Literal) and x.type in types and x.value == value

        res = None
        if op == "+":
            if is_lit(r, 0, NUM) and l.type == e.type: res = l
            elif is_lit(l, 0, NUM) and r.type == e.type: res = r
        elif op == "-":
            if is_lit(r, 0, NUM) and l.type == e.type: res = l
        elif op == "*":
            if is_lit(r, 1, NUM) and l.type == e.type: res = l
            elif is_lit(l, 1, NUM) and r.type == e.type: res = r
            elif e.type == "int" and ((is_lit(r, 0, ("int",)) and not has_call(l)) or
                                      (is_lit(l, 0, ("int",)) and not has_call(r))):
                res = Literal(0, type="int", line=e.line, col=e.col)
        elif op == "/":
            if is_lit(r, 1, NUM) and l.type == e.type: res = l
        elif op == "&&":
            if is_lit(r, True, ("bool",)): res = l
            elif is_lit(l, True, ("bool",)): res = r
            elif is_lit(l, False, ("bool",)): res = l
            elif is_lit(r, False, ("bool",)) and not has_call(l): res = r
        elif op == "||":
            if is_lit(r, False, ("bool",)): res = l
            elif is_lit(l, False, ("bool",)): res = r
            elif is_lit(l, True, ("bool",)): res = l
            elif is_lit(r, True, ("bool",)) and not has_call(l): res = r
        if res is None:
            return e
        self.note(e, "algebraic simplification", f"{show(e)} → {show(res)}")
        return res

    # ---- dead-code elimination: unused constants ----
    def remove_unused_consts(self, prog):
        uses = {}
        for n in iter_nodes(prog):
            if isinstance(n, Identifier):
                uses[n.name] = uses.get(n.name, 0) + 1
            elif isinstance(n, Assign):
                uses[n.name] = uses.get(n.name, 0) + 1
        prog.body = self.prune(prog.body, uses)

    def prune(self, body, uses):
        out = []
        for s in body:
            if isinstance(s, VarDecl) and s.is_const and uses.get(s.name, 0) == 0 and not has_call(s.init):
                self.note(s, "dead-code elimination", f"removed unused constant '{s.name}'")
                continue
            for attr in ("body", "then_body", "else_body"):
                v = getattr(s, attr, None)
                if isinstance(v, list):
                    setattr(s, attr, self.prune(v, uses))
            if isinstance(s, If) and s.else_body == []:
                s.else_body = None
            out.append(s)
        return out


def optimize_program(program):
    opt = Optimizer()
    result = opt.run(program)
    return result, opt.log
