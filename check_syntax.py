import ast
import sys

def check_syntax(filepath):
    with open(filepath, "r") as f:
        source = f.read()
    try:
        ast.parse(source)
        print(f"Syntax OK: {filepath}")
    except SyntaxError as e:
        print(f"Syntax Error in {filepath}: {e}")
        sys.exit(1)

check_syntax("src/pharmabot/gui/pages/scraper.py")
