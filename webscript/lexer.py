"""Phase 1 - Lexical analysis: source text -> list of tokens."""
import json
from dataclasses import dataclass

from .errors import CompileError

KEYWORDS = {
    "let", "const", "fn", "if", "else", "while", "for", "in", "range",
    "return", "print", "true", "false", "int", "float", "string", "bool",
}

OPS2 = {"==": "EQ", "!=": "NEQ", "<=": "LTE", ">=": "GTE",
        "&&": "AND", "||": "OR", "->": "ARROW"}
OPS1 = {"+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH", "%": "PERCENT",
        "<": "LT", ">": "GT", "=": "ASSIGN", "!": "NOT",
        "(": "LPAREN", ")": "RPAREN", "{": "LBRACE", "}": "RBRACE",
        ",": "COMMA", ":": "COLON", ";": "SEMI"}

ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
DIGITS = "0123456789"


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def display(self):
        if self.type == "EOF":
            return "EOF"
        if self.type == "STRING":
            return f"STRING({json.dumps(self.value, ensure_ascii=False)})"
        return f"{self.type}({self.value})"

    def to_dict(self):
        return {"type": self.type, "value": self.value, "line": self.line,
                "col": self.col, "display": self.display()}


def _is_alpha(c):
    return c == "_" or ("a" <= c <= "z") or ("A" <= c <= "Z")


def tokenize(src):
    tokens = []
    i, n = 0, len(src)
    line, line_start = 1, 0

    def err(msg, at_line, at_col):
        raise CompileError("Lexical", msg, at_line, at_col)

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            line_start = i
            continue
        if c in " \t\r":
            i += 1
            continue
        if src.startswith("//", i):                      # comment
            while i < n and src[i] != "\n":
                i += 1
            continue

        col = i - line_start + 1

        if _is_alpha(c):                                 # identifier / keyword
            j = i
            while j < n and (_is_alpha(src[j]) or src[j] in DIGITS):
                j += 1
            word = src[i:j]
            tokens.append(Token("KEYWORD" if word in KEYWORDS else "IDENTIFIER",
                                word, line, col))
            i = j
            continue

        if c in DIGITS:                                  # number
            j = i
            while j < n and src[j] in DIGITS:
                j += 1
            is_float = False
            if j < n and src[j] == "." and j + 1 < n and src[j + 1] in DIGITS:
                is_float = True
                j += 1
                while j < n and src[j] in DIGITS:
                    j += 1
            if j < n and (_is_alpha(src[j]) or src[j] == "."):
                end = j
                while end < n and (_is_alpha(src[end]) or src[end] in DIGITS or src[end] == "."):
                    end += 1
                err(f"Malformed number literal '{src[i:end]}'", line, col)
            tokens.append(Token("FLOAT" if is_float else "INT", src[i:j], line, col))
            i = j
            continue

        if c == '"':                                     # string
            j, buf = i + 1, []
            while True:
                if j >= n or src[j] == "\n":
                    err("Unterminated string literal", line, col)
                ch = src[j]
                if ch == '"':
                    break
                if ch == "\\":
                    esc = src[j + 1] if j + 1 < n else ""
                    if esc == "" or esc not in ESCAPES:
                        err(f"Invalid escape sequence '\\{esc}' in string", line, j - line_start + 1)
                    buf.append(ESCAPES[esc])
                    j += 2
                    continue
                buf.append(ch)
                j += 1
            tokens.append(Token("STRING", "".join(buf), line, col))
            i = j + 1
            continue

        two = src[i:i + 2]
        if two in OPS2:
            tokens.append(Token(OPS2[two], two, line, col))
            i += 2
            continue
        if c in OPS1:
            tokens.append(Token(OPS1[c], c, line, col))
            i += 1
            continue

        err(f"Invalid character '{c}'", line, col)

    tokens.append(Token("EOF", "", line, i - line_start + 1))
    return tokens
