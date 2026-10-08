"""Command line use:  python -m webscript examples/proposal_example.ws [--no-opt] [--run]"""
import argparse
import shutil
import subprocess
import sys

from . import compile_source


def section(title):
    print(f"\n=== {title} " + "=" * max(3, 60 - len(title)))


def main():
    ap = argparse.ArgumentParser(prog="webscript", description="WebScript -> JavaScript compiler")
    ap.add_argument("file")
    ap.add_argument("--no-opt", action="store_true", help="skip the optimization phase")
    ap.add_argument("--run", action="store_true", help="run the generated JavaScript with node (if installed)")
    args = ap.parse_args()

    with open(args.file, encoding="utf-8") as f:
        res = compile_source(f.read(), optimize=not args.no_opt)
    ph = res["phases"]

    if ph["lexical"]["status"] == "ok":
        section("1. Tokens")
        print("  ".join(t["display"] for t in ph["lexical"]["tokens"]))
    if ph["syntax"]["status"] == "ok":
        section("2. AST")
        print(ph["syntax"]["ast"])
    if ph["semantic"]["status"] != "skipped":
        section("3. Symbol table")
        for s in ph["semantic"]["symbols"]:
            print(f"{s['name']:<14}{s['type']:<10}{s['kind']:<14}{s['scope']:<22}{s['info']}")
    if ph["ir"]["status"] == "ok":
        section("4. Intermediate code")
        print("\n".join(ph["ir"]["lines"]))
        section("5. Optimization log")
        print("\n".join(ph["optimization"]["log"]) or "(nothing to optimize)")
        section("5. Optimized intermediate code")
        print("\n".join(ph["optimization"]["lines"]))
        section("6. Generated JavaScript")
        print(ph["codegen"]["js"])

    for e in res["errors"]:
        print(f"{e['phase']} Error at line {e['line']}, col {e['col']}: {e['message']}", file=sys.stderr)
    if not res["ok"]:
        sys.exit(1)

    if args.run:
        node = shutil.which("node")
        if not node:
            print("node is not installed - skipping --run", file=sys.stderr)
            sys.exit(2)
        section("Program output")
        sys.stdout.flush()
        subprocess.run([node, "-e", ph["codegen"]["js"]])


if __name__ == "__main__":
    main()
