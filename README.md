# WebScript – a small compiler that generates JavaScript

Course project for *4CS501CC25 – Principles of Compiler Design*.
Python compiler + Flask web interface that shows every compiler phase.

```
source → Lexer → Parser (AST) → Semantic analyzer (+ symbol table)
       → Intermediate code (3-address) → Optimizer → JavaScript generator
```

## 1. Set up the Ubuntu VM

### Quick way
```bash
sudo apt update && sudo apt install -y unzip
unzip webscript-compiler.zip && cd webscript-compiler
bash setup_ubuntu.sh
```

### Manual way (same thing, step by step)
```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv unzip nodejs
git --version && python3 --version        # check they installed
node --version                            # optional (see "Optional" below)

cd webscript-compiler
python3 -m venv venv                      # a venv is required on Ubuntu 24.04
source venv/bin/activate                  # prompt now starts with (venv)
pip install -r requirements.txt           # installs Flask
```
Re-run `source venv/bin/activate` every time you open a new terminal.

## 2. Run it
```bash
source venv/bin/activate
python app.py                  # open http://127.0.0.1:5000 in the VM's browser
```
Browsing from your *host* machine instead? Run `HOST=0.0.0.0 python app.py`
and open `http://<VM-IP>:5000` (find the IP with `hostname -I`).

Command-line version (no browser needed):
```bash
python -m webscript examples/03_optimizer_demo.ws          # print every phase
python -m webscript examples/02_functions_and_loops.ws --run   # also execute (needs node)
python -m webscript examples/03_optimizer_demo.ws --no-opt     # without optimization
```

## 3. Test
```bash
python -m unittest discover -s tests -v
```
(The two execution tests are skipped automatically if `node` is not installed.)

## 4. Put it under Git
```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
git init
git add .
git commit -m "WebScript compiler: lexer, parser, semantic, IR, optimizer, codegen, UI"
```

## The WebScript language
```
// comments
let x = 10                 // variable, type inferred (int, float, string, bool)
let y: float = 3           // optional type annotation (int → float is allowed)
const MAX = 100            // constant
x = x + 1                  // assignment

if x > 5 { ... } else if x > 2 { ... } else { ... }
while x < 20 { ... }
for i in range(1, 6) { ... }          // i = 1..5     (range(5) = 0..4)

fn add(a: int, b: int) -> int { return a + b }     // no "->" = returns nothing
fn hello(name: string) { print("Hi " + name) }

print("a", 1, true)        // output
str(42)                    // built-in: value → string
```
Operators: `+ - * / %`, `< > <= >= == !=`, `&& || !`.
`int / int` is integer division (like `Math.trunc(a / b)` in the generated JS).
Semicolons are optional.

## Project layout
| File | Phase |
|---|---|
| `webscript/lexer.py` | Lexical analysis → tokens |
| `webscript/parser.py`, `ast_nodes.py` | Syntax analysis → AST |
| `webscript/semantic.py` | Semantic analysis, symbol table, type checking |
| `webscript/ir.py` | Three-address intermediate code |
| `webscript/optimizer.py` | Constant folding / propagation, algebraic simplification, dead-code elimination |
| `webscript/codegen.py` | JavaScript generation |
| `webscript/compiler.py` | Runs the pipeline, returns every phase's output |
| `app.py`, `static/index.html` | Flask server + interactive UI |
| `examples/*.ws` | Demo programs (3 valid, 3 with lexical / syntax / semantic errors) |
| `tests/test_compiler.py` | 23 unit tests |

## Notes / design decisions
* The optimizer works on the AST; the "Optimized" tab shows the optimizer's log
  plus the three-address code of the optimized program. JavaScript is generated from the optimized AST.
* Constant propagation applies to `const` only, so `let` variables look exactly as written.
* Generated JavaScript runs in the browser inside a Web Worker with a 3-second timeout (infinite loops can't freeze the page).
