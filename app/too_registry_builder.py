import os

UTILS_DIR = "utils"
import ast
from typing import Dict, Any, Optional


def parse_argparse_from_main(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse the argparse.ArgumentParser description and arguments from main() in the file."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filepath)

    # Find main() function definition
    main_func = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            main_func = node
            break
    if main_func is None:
        return None

    parser_desc = ""
    args_info = {}

    # Find ArgumentParser instance and calls to add_argument()
    # We'll track the variable assigned to ArgumentParser() and search calls on it.
    parser_vars = set()
    for stmt in main_func.body:
        # Look for: parser = argparse.ArgumentParser(...)
        if isinstance(stmt, ast.Assign):
            val = stmt.value
            if (
                    isinstance(val, ast.Call)
                    and getattr(val.func, "attr", "") == "ArgumentParser"
            ):
                # Found parser assignment
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        parser_vars.add(target.id)
                # Extract description kwarg
                for kw in val.keywords:
                    if kw.arg == "description":
                        if isinstance(kw.value, ast.Str):
                            parser_desc = kw.value.s

        # Look for calls to parser.add_argument(...)
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            func = call.func
            if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "add_argument"
                    and isinstance(func.value, ast.Name)
                    and func.value.id in parser_vars
            ):
                # Extract argument details
                # Arg name is first positional argument or keywords
                arg_names = []
                if call.args:
                    for a in call.args:
                        if isinstance(a, ast.Str):
                            arg_names.append(a.s)
                # Use first arg name that starts with "--" as optional, else positional
                # For simplicity, we'll only parse the first argument here.
                if not arg_names:
                    continue
                arg_name = arg_names[0].lstrip("-")

                # Defaults
                optional = True if arg_names[0].startswith("-") else False
                help_str = ""
                nargs = None
                default_val = None

                for kw in call.keywords:
                    if kw.arg == "help" and isinstance(kw.value, ast.Str):
                        help_str = kw.value.s
                    if kw.arg == "nargs" and isinstance(kw.value, ast.Str):
                        nargs = kw.value.s
                    if kw.arg == "default":
                        default_val = True  # presence means default is set

                # Optional if nargs="?" or default is set or if argument name starts with -
                if nargs == "?" or default_val is not None or arg_names[0].startswith("-"):
                    optional = True
                else:
                    optional = False

                args_info[arg_name] = {
                    "optional": optional,
                    "description": help_str,
                }

    if not args_info and not parser_desc:
        return None
    return {
        "description": parser_desc,
        "parameters": args_info,
    }


def build_tools_registry(utils_dir: str = "utils") -> Dict[str, Any]:
    registry = {}
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    utils_dir = os.path.join(root_dir, utils_dir)
    for filename in os.listdir(utils_dir):
        # filename = "find_user_by_job_title.py"
        if filename.endswith(".py") and not filename.startswith("__"):
            filepath = os.path.join(utils_dir, filename)

            # Try to extract argparse info from main()
            argparse_info = parse_argparse_from_main(filepath)
            if argparse_info:
                # Use filename (without .py) as tool name key
                tool_name = os.path.splitext(filename)[0]
                registry[tool_name] = argparse_info
            else:
                # fallback to function metadata as before
                # ... your existing fallback logic here ...
                pass
    return registry


if __name__ == "__main__":
    import json

    registry = build_tools_registry()
    print(json.dumps(registry, indent=2))
