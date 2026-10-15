"""Non-interactive content management and gated build commands."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

from . import __version__
from .core.content import ContentError, KnowledgeBase


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ContentError(message, "ARGUMENT_ERROR", 2)


def parser():
    p = Parser(description="Maintain and build an English-first bilingual knowledge base")
    p.add_argument("--config", default="mkdocs.yml")
    p.add_argument("--data-dir", default=os.getenv("KBTOOL_DATA_DIR"))
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--version", action="store_true")
    commands = p.add_subparsers(dest="command")
    commands.add_parser("check")
    commands.add_parser("missing-translations")
    new = commands.add_parser("new-page")
    new.add_argument("slug")
    new.add_argument("--section", default="")
    new.add_argument("--title")
    build = commands.add_parser("build")
    build.add_argument("--out")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    export = commands.add_parser("export")
    export.add_argument("--format", choices=["json", "csv"], default="json")
    export.add_argument("--out", required=True)
    export.add_argument("--no-bom", action="store_true")
    imp = commands.add_parser("import")
    imp.add_argument("path")
    imp.add_argument("--yes", action="store_true")
    commands.add_parser("backup")
    return p


def globals_first(argv):
    globals, rest = [], []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in {"--config", "--data-dir"}:
            if i + 1 == len(argv):
                raise ContentError(f"{token} requires a value")
            globals += argv[i : i + 2]
            i += 2
        elif token in {"--json", "--quiet", "--version"} or token.startswith(
            ("--config=", "--data-dir=")
        ):
            globals.append(token)
            i += 1
        else:
            rest.append(token)
            i += 1
    return globals + rest


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    json_mode = "--json" in raw
    try:
        args = parser().parse_args(globals_first(raw))
        if args.version:
            data = {"version": __version__}
        else:
            if not args.command:
                raise ContentError("A command is required", "ARGUMENT_ERROR")
            kb = KnowledgeBase(args.config, args.data_dir)
            command = args.command
            if command == "check":
                data = kb.check()
                if not data["passed"]:
                    print(
                        json.dumps(
                            {
                                "ok": False,
                                "error": {
                                    "code": "SENSITIVE_CONTENT",
                                    "message": "Sensitive-content gate failed",
                                },
                                "data": data,
                            }
                        )
                        if json_mode
                        else json.dumps(data, indent=2)
                    )
                    return 1
            elif command == "missing-translations":
                data = kb.missing()
            elif command == "new-page":
                data = kb.new_page(args.slug, args.section, args.title)
            elif command == "export":
                data = kb.export(args.out, args.format, not args.no_bom)
            elif command == "import":
                data = kb.import_data(args.path, args.yes)
            elif command == "backup":
                data = kb.backup()
            elif command in {"build", "serve"}:
                result = kb.check()
                if not result["passed"]:
                    raise ContentError(
                        "Sensitive-content gate failed; run kbtool check --json for locations",
                        "SENSITIVE_CONTENT",
                        1,
                    )
                call = [sys.executable, "-m", "mkdocs", command, "-f", str(kb.config_path)]
                if command == "build":
                    call += ["--strict"]
                    if args.out:
                        call += ["--site-dir", str(Path(args.out).resolve())]
                else:
                    call += ["--dev-addr", f"{args.host}:{args.port}"]
                env = os.environ.copy()
                if args.data_dir:
                    env["KBTOOL_DATA_DIR"] = str(kb.data)
                proc = subprocess.run(call, cwd=kb.root, env=env, stdout=sys.stderr)
                if proc.returncode:
                    raise ContentError("MkDocs failed; inspect stderr", "BUILD_FAILED", 1)
                data = {
                    "site_dir": str(
                        Path(args.out).resolve()
                        if command == "build" and args.out
                        else kb.root / kb.config.get("site_dir", "site")
                    )
                }
        if json_mode:
            print(json.dumps({"ok": True, "data": data, "warnings": []}, ensure_ascii=False))
        elif not args.quiet:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    except ContentError as exc:
        print(
            json.dumps({"ok": False, "error": {"code": exc.code, "message": str(exc)}})
            if json_mode
            else str(exc),
            file=sys.stdout if json_mode else sys.stderr,
        )
        return exc.exit_code
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, re.error) as exc:
        print(
            json.dumps({"ok": False, "error": {"code": "OPERATION_FAILED", "message": str(exc)}})
            if json_mode
            else str(exc),
            file=sys.stdout if json_mode else sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
