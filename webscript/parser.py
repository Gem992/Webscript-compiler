"""Phase 2 - Syntax analysis: tokens -> AST (recursive descent).

Grammar (informal):
  program    := (function | statement)* EOF
  function   := 'fn' IDENT '(' [param (',' param)*] ')' ['->' TYPE] block
  param      := IDENT ':' TYPE
  statement  := ('let'|'const') IDENT [':' TYPE] '=' expr
              | IDENT '=' expr
              | 'if' expr block ['else' (if-statement | block)]
              | 'while' expr block
              | 'for' IDENT 'in' 'range' '(' expr [',' expr] ')' block
              | 'return' [expr]
              | 'print' '(' expr (',' expr)* ')'
              | call
  block      := '{' statement* '}'
  expr       := or  ->  and  ->  equality  ->  comparison  ->  term  ->  factor  ->  unary  ->  primary
"""
import json

from .ast_nodes import (Assign, Binary, Call, ExprStmt, ForRange, FunctionDecl,
                        Identifier, If, Literal, Param, Print, Program, Return,
                        Unary, VarDecl, While)
from .errors import CompileError

TYPES = {"int", "float", "string", "bool"}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---- token helpers ----
    def peek(self, k=0):
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

    def advance(self):
        tok = self.peek()
        if tok.type != "EOF":
            self.pos += 1
        return tok

    def check(self, type_, value=None, k=0):
        t = self.peek(k)
        return t.type == type_ and (value is None or t.value == value)

    def match(self, type_, value=None):
        return self.advance() if self.check(type_, value) else None

    @staticmethod
    def describe(tok):
        if tok.type == "EOF":
            return "end of file"
        if tok.type == "STRING":
            return json.dumps(tok.value, ensure_ascii=False)
        return f"'{tok.value}'"

    def error(self, msg, tok=None):
        tok = tok or self.peek()
        raise CompileError("Syntax", msg, tok.line, tok.col)

    def expect(self, type_, what, value=None):
        if self.check(type_, value):
            return self.advance()
        self.error(f"Expected {what} but found {self.describe(self.peek())}")

    # ---- program / declarations ----
    def parse_program(self):
        body = []
        while not self.check("EOF"):
            if self.check("KEYWORD", "fn"):
                body.append(self.function())
            else:
                body.append(self.statement())
        return Program(body, line=1, col=1)

    def parse_type(self):
        t = self.peek()
        if t.type == "KEYWORD" and t.value in TYPES:
            return self.advance().value
        self.error(f"Expected a type name (int, float, string, bool) but found {self.describe(t)}")

    def function(self):
        start = self.advance()                       # 'fn'
        name = self.expect("IDENTIFIER", "a function name").value
        self.expect("LPAREN", "'('")
        params = []
        if not self.check("RPAREN"):
            while True:
                p = self.expect("IDENTIFIER", "a parameter name")
                self.expect("COLON", "':' after parameter name")
                params.append(Param(p.value, self.parse_type(), line=p.line, col=p.col))
                if not self.match("COMMA"):
                    break
        self.expect("RPAREN", "')'")
        ret = self.parse_type() if self.match("ARROW") else None
        body = self.block()
        return FunctionDecl(name, params, ret, body, line=start.line, col=start.col)

    # ---- statements ----
    def block(self):
        self.expect("LBRACE", "'{'")
        stmts = []
        while not self.check("RBRACE"):
            if self.check("EOF"):
                self.error("Missing closing '}' before end of file")
            stmts.append(self.statement())
        self.advance()
        return stmts

    def statement(self):
        t = self.peek()
        if t.type == "KEYWORD":
            handlers = {"let": self.var_decl, "const": self.var_decl, "if": self.if_stmt,
                        "while": self.while_stmt, "for": self.for_stmt,
                        "return": self.return_stmt, "print": self.print_stmt}
            if t.value in handlers:
                node = handlers[t.value]()
                self.match("SEMI")
                return node
            if t.value == "fn":
                self.error("Functions can only be declared at the top level")
            self.error(f"Unexpected keyword {self.describe(t)}")
        if t.type == "IDENTIFIER":
            if self.check("ASSIGN", k=1):
                self.advance(); self.advance()
                node = Assign(t.value, self.expression(), line=t.line, col=t.col)
            elif self.check("LPAREN", k=1):
                node = ExprStmt(self.expression(), line=t.line, col=t.col)
            else:
                self.error(f"Expected '=' or '(' after '{t.value}' but found {self.describe(self.peek(1))}",
                           self.peek(1))
            self.match("SEMI")
            return node
        self.error(f"Unexpected {self.describe(t)}; expected a statement")

    def var_decl(self):
        kw = self.advance()
        name = self.expect("IDENTIFIER", "a variable name").value
        declared = self.parse_type() if self.match("COLON") else None
        self.expect("ASSIGN", "'=' (variables must be initialised)")
        init = self.expression()
        return VarDecl(name, kw.value == "const", declared, init, line=kw.line, col=kw.col)

    def if_stmt(self):
        kw = self.advance()
        cond = self.expression()
        then_body = self.block()
        else_body = None
        if self.match("KEYWORD", "else"):
            else_body = [self.if_stmt()] if self.check("KEYWORD", "if") else self.block()
        return If(cond, then_body, else_body, line=kw.line, col=kw.col)

    def while_stmt(self):
        kw = self.advance()
        cond = self.expression()
        return While(cond, self.block(), line=kw.line, col=kw.col)

    def for_stmt(self):
        kw = self.advance()
        var = self.expect("IDENTIFIER", "a loop variable name").value
        self.expect("KEYWORD", "'in'", "in")
        self.expect("KEYWORD", "'range'", "range")
        self.expect("LPAREN", "'('")
        first = self.expression()
        if self.match("COMMA"):
            start, end = first, self.expression()
        else:
            start, end = Literal(0, type="int", line=kw.line, col=kw.col), first
        self.expect("RPAREN", "')'")
        return ForRange(var, start, end, self.block(), line=kw.line, col=kw.col)

    def return_stmt(self):
        kw = self.advance()
        nxt = self.peek()
        if nxt.type in ("RBRACE", "SEMI", "EOF") or nxt.line != kw.line:
            return Return(None, line=kw.line, col=kw.col)
        return Return(self.expression(), line=kw.line, col=kw.col)

    def print_stmt(self):
        kw = self.advance()
        self.expect("LPAREN", "'(' after print")
        args = [self.expression()]
        while self.match("COMMA"):
            args.append(self.expression())
        self.expect("RPAREN", "')'")
        return Print(args, line=kw.line, col=kw.col)

    # ---- expressions (lowest -> highest precedence) ----
    def _binary_level(self, next_level, types):
        left = next_level()
        while self.peek().type in types:
            op = self.advance()
            left = Binary(op.value, left, next_level(), line=op.line, col=op.col)
        return left

    def expression(self):
        return self._binary_level(self.and_expr, ("OR",))

    def and_expr(self):
        return self._binary_level(self.equality, ("AND",))

    def equality(self):
        return self._binary_level(self.comparison, ("EQ", "NEQ"))

    def comparison(self):
        return self._binary_level(self.term, ("LT", "GT", "LTE", "GTE"))

    def term(self):
        return self._binary_level(self.factor, ("PLUS", "MINUS"))

    def factor(self):
        return self._binary_level(self.unary, ("STAR", "SLASH", "PERCENT"))

    def unary(self):
        if self.peek().type in ("MINUS", "NOT"):
            op = self.advance()
            return Unary(op.value, self.unary(), line=op.line, col=op.col)
        return self.primary()

    def primary(self):
        t = self.peek()
        if t.type == "INT":
            self.advance()
            return Literal(int(t.value), type="int", line=t.line, col=t.col)
        if t.type == "FLOAT":
            self.advance()
            return Literal(float(t.value), type="float", line=t.line, col=t.col)
        if t.type == "STRING":
            self.advance()
            return Literal(t.value, type="string", line=t.line, col=t.col)
        if t.type == "KEYWORD" and t.value in ("true", "false"):
            self.advance()
            return Literal(t.value == "true", type="bool", line=t.line, col=t.col)
        if t.type == "IDENTIFIER":
            self.advance()
            if self.match("LPAREN"):
                args = []
                if not self.check("RPAREN"):
                    args.append(self.expression())
                    while self.match("COMMA"):
                        args.append(self.expression())
                self.expect("RPAREN", "')' after arguments")
                return Call(t.value, args, line=t.line, col=t.col)
            return Identifier(t.value, line=t.line, col=t.col)
        if t.type == "LPAREN":
            self.advance()
            e = self.expression()
            self.expect("RPAREN", "')'")
            return e
        self.error(f"Expected an expression but found {self.describe(t)}")


def parse(tokens):
    return Parser(tokens).parse_program()
