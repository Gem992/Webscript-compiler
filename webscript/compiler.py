"""Runs the whole pipeline and returns the output of every phase as a dict (JSON-friendly)."""
from .ast_nodes import tree_text
from .codegen import generate_js
from .errors import CompileError
from .ir import generate_ir
from .lexer import tokenize
from .optimizer import optimize_program
from .parser import parse
from .semantic import CATEGORIES, SemanticAnalyzer

PHASES = ["lexical", "syntax", "semantic", "ir", "optimization", "codegen"]


def compile_source(source, optimize=True):
    result = {"ok": False, "errors": [], "phases": {p: {"status": "skipped"} for p in PHASES}}
    ph = result["phases"]

    # 1. lexical analysis
    try:
        tokens = tokenize(source)
    except CompileError as e:
        ph["lexical"] = {"status": "error", "tokens": []}
        result["errors"].append(e.to_dict())
        return result
    ph["lexical"] = {"status": "ok", "tokens": [t.to_dict() for t in tokens]}

    # 2. syntax analysis
    try:
        program = parse(tokens)
    except CompileError as e:
        ph["syntax"] = {"status": "error", "ast": ""}
        result["errors"].append(e.to_dict())
        return result
    ph["syntax"] = {"status": "ok", "ast": tree_text(program)}

    # 3. semantic analysis (+ symbol table)
    errors, symbols = SemanticAnalyzer().analyze(program)
    failed = {e.category for e in errors}
    ph["semantic"] = {
        "status": "error" if errors else "ok",
        "checks": [{"name": c, "passed": c not in failed} for c in CATEGORIES],
        "symbols": [s.to_dict() for s in symbols],
        "typed_ast": tree_text(program),
    }
    if errors:
        result["errors"] += [e.to_dict() for e in errors]
        return result

    # 4. intermediate code
    ph["ir"] = {"status": "ok", "lines": generate_ir(program)}

    # 5. optimization
    final = program
    if optimize:
        final, log = optimize_program(program)
        ph["optimization"] = {"status": "ok", "log": log, "lines": generate_ir(final)}
    else:
        ph["optimization"] = {"status": "skipped", "log": [], "lines": [],
                              "note": "Optimization is switched off."}

    # 6. code generation
    ph["codegen"] = {"status": "ok", "js": generate_js(final)}
    result["ok"] = True
    return result
