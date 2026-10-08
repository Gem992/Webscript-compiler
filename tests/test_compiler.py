import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from webscript import compile_source  # noqa: E402

PROPOSAL = '''let name = "Veer"
let age = 20
if age >= 18 {
    print("Adult")
} else {
    print("Minor")
}
'''


def js(src, optimize=True):
    res = compile_source(src, optimize)
    assert res["ok"], res["errors"]
    return res["phases"]["codegen"]["js"]


def errors(src):
    return [e["message"] for e in compile_source(src)["errors"]]


class LexerTests(unittest.TestCase):
    def test_tokens_of_let(self):
        toks = compile_source("let age = 20")["phases"]["lexical"]["tokens"]
        self.assertEqual([t["display"] for t in toks],
                         ["KEYWORD(let)", "IDENTIFIER(age)", "ASSIGN(=)", "INT(20)", "EOF"])

    def test_invalid_character(self):
        res = compile_source("let x = 5 # 3")
        self.assertFalse(res["ok"])
        self.assertEqual(res["errors"][0]["phase"], "Lexical")
        self.assertEqual((res["errors"][0]["line"], res["errors"][0]["col"]), (1, 11))

    def test_malformed_number_and_string(self):
        self.assertIn("Malformed number", errors("let x = 12abc")[0])
        self.assertIn("Unterminated string", errors('let x = "abc')[0])


class ParserTests(unittest.TestCase):
    def test_missing_brace(self):
        self.assertIn("Missing closing '}'", errors("if true {\n print(1)\n")[0])

    def test_missing_initialiser(self):
        self.assertIn("Expected '='", errors("let x")[0])

    def test_precedence(self):
        self.assertEqual(js("print(1 + 2 * 3)", False), "console.log(1 + 2 * 3);\n")
        self.assertEqual(js("print((1 + 2) * 3)", False), "console.log((1 + 2) * 3);\n")


class SemanticTests(unittest.TestCase):
    def test_type_mismatch_message_from_proposal(self):
        e = errors('let age = 20\nage = "hello"')
        self.assertEqual(e, ["Cannot assign a string value to integer variable 'age'."])

    def test_undeclared_and_duplicate(self):
        e = errors("print(y)\nlet a = 1\nlet a = 2")
        self.assertTrue(any("undeclared variable 'y'" in m for m in e))
        self.assertTrue(any("Duplicate declaration of 'a'" in m for m in e))

    def test_function_checks(self):
        src = "fn f(a: int) -> int { return a }\nprint(f(1, 2))\nprint(f(\"x\"))\ng()"
        e = errors(src)
        self.assertTrue(any("expects 1 argument" in m for m in e))
        self.assertTrue(any("Argument 1" in m for m in e))
        self.assertTrue(any("undeclared function 'g'" in m for m in e))

    def test_const_and_condition_and_division(self):
        e = errors("const c = 1\nc = 2\nif 5 { print(1) }\nprint(1 / 0)")
        self.assertEqual(len(e), 3)

    def test_int_to_float_ok_float_to_int_not(self):
        self.assertTrue(compile_source("let x: float = 3")["ok"])
        self.assertFalse(compile_source("let x: int = 3.5")["ok"])

    def test_symbol_table(self):
        syms = compile_source('let name = "Veer"\nlet age = 20')["phases"]["semantic"]["symbols"]
        self.assertEqual([(s["name"], s["type"], s["kind"]) for s in syms],
                         [("name", "string", "variable"), ("age", "integer", "variable")])


class BackendTests(unittest.TestCase):
    def test_proposal_example(self):
        expected = ('let name = "Veer";\nlet age = 20;\nif (age >= 18) {\n'
                    '    console.log("Adult");\n} else {\n    console.log("Minor");\n}\n')
        self.assertEqual(js(PROPOSAL), expected)

    def test_ir(self):
        lines = compile_source("let x = 10\nlet y = 20\nlet z = x + y")["phases"]["ir"]["lines"]
        self.assertEqual([l.strip() for l in lines], ["x = 10", "y = 20", "t1 = x + y", "z = t1"])

    def test_constant_folding(self):
        self.assertEqual(js("let x = 10 + 20"), "let x = 30;\n")

    def test_algebraic_and_dead_code(self):
        out = js("let a = 4\nlet b = a * 1 + 0\nif false { print(1) }\nwhile false { print(2) }")
        self.assertEqual(out, "let a = 4;\nlet b = a;\n")

    def test_constant_propagation_and_unused_const(self):
        out = js("const N = 5\nconst M = N * 2\nprint(M)")
        self.assertEqual(out, "console.log(10);\n")

    def test_no_optimization_switch(self):
        self.assertEqual(js("let x = 10 + 20", optimize=False), "let x = 10 + 20;\n")

    def test_integer_division(self):
        self.assertEqual(js("let a = 7\nprint(a / 2)", False),
                         "let a = 7;\nconsole.log(Math.trunc(a / 2));\n")

    def test_const_float_propagation_keeps_float_division(self):
        out = js("const h: float = 3\nprint(h / 2)")
        self.assertEqual(out, "console.log(1.5);\n")

    def test_else_if(self):
        out = js("let x = 1\nif x < 0 { print(1) } else if x < 5 { print(2) } else { print(3) }")
        self.assertIn("} else if (x < 5) {", out)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ExecutionTests(unittest.TestCase):
    def run_js(self, src, optimize=True):
        out = subprocess.run(["node", "-e", js(src, optimize)], capture_output=True, text=True)
        return out.stdout.strip()

    def test_factorial_both_modes(self):
        src = ("fn f(n: int) -> int {\n if n <= 1 { return 1 }\n return n * f(n - 1)\n}\n"
               "print(f(5))")
        self.assertEqual(self.run_js(src), "120")
        self.assertEqual(self.run_js(src, False), "120")

    def test_examples_run(self):
        folder = os.path.join(os.path.dirname(__file__), "..", "examples")
        for name in sorted(os.listdir(folder)):
            if name.startswith(("01", "02", "03")):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    src = f.read()
                self.assertEqual(self.run_js(src), self.run_js(src, False), name)


if __name__ == "__main__":
    unittest.main()
