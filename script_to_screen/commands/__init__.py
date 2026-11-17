"""Commands: the only way anything is done to a show from outside.

Every command is declared once, with its arguments, a one-line summary and an example. The
command line is generated from the declarations (and so will the MCP server be). A command:

  - never asks a question: it runs, or it refuses and says what to do instead
  - can answer in JSON (`--json`), and a change can be rehearsed (`--dry-run`)
  - returns what changed, what is now wrong, and how to look at the result

Exit codes: 0 done, 2 refused (nothing changed), 3 the show has errors (check, render, parity).
"""
import argparse
import json
import sys

import yaml

from ..script import ScriptError

OK, REFUSED, FAILED = 0, 2, 3
COMMANDS = {}


class Refused(Exception):
    """The command did nothing. `hint` says what would work."""

    def __init__(self, msg, hint=None, **more):
        super().__init__(msg)
        self.hint, self.more = hint, more


def A(name, help, **kw):
    """One argument. A name starting with `--` is an option; anything else is positional."""
    return dict(name=name, help=help, kw=kw)


def command(name, summary, args=(), example=None, changes=False, group="read"):
    def wrap(fn):
        COMMANDS[name] = dict(name=name, summary=summary, args=list(args), example=example, changes=changes,
                              group=group, fn=fn)
        return fn
    return wrap


def describe(c):
    return dict(name=c["name"], group=c["group"], summary=c["summary"], changes=c["changes"], example=c["example"],
                args=[dict(name=a["name"], help=a["help"], required=not a["name"].startswith("--") and a["kw"].get("nargs") not in ("?", "*"),
                           choices=a["kw"].get("choices")) for a in c["args"]]
                + ([dict(name="--dry-run", help="Report what would change and what would then be wrong; change nothing", required=False, choices=None),
                    dict(name="--because", help="The writer's own words that caused this change; kept in the journal", required=False, choices=None),
                    dict(name="--force", help="Apply even if the change introduces an error", required=False, choices=None)] if c["changes"] else []))


def parser():
    top = argparse.ArgumentParser(prog="s2s", description="script-to-screen: a script goes in, a rendered episode comes out.")
    sub = top.add_subparsers(dest="command", metavar="<command>")
    for c in COMMANDS.values():
        p = sub.add_parser(c["name"], help=c["summary"], description=c["summary"],
                           epilog=("example:  " + c["example"]) if c["example"] else None)
        for a in c["args"]:
            p.add_argument(a["name"], help=a["help"], **a["kw"])
        p.add_argument("--json", action="store_true", help="answer as JSON")
        p.add_argument("--show", help="the show's folder (default: found from the scene, or from here)")
        if c["changes"]:
            p.add_argument("--dry-run", action="store_true", help="report what would change; change nothing")
            p.add_argument("--because", help="the writer's own words that caused this change")
            p.add_argument("--force", action="store_true", help="apply even if the change introduces an error")
    return top


def run(argv=None):
    from . import change, look, notes, read, structure, tune  # noqa: F401  (declares the commands)
    top = parser()
    a = top.parse_args(argv)
    if not a.command:
        top.print_help()
        return REFUSED
    c = COMMANDS[a.command]
    try:
        out = c["fn"](a) or {}
        out = dict(ok=out.pop("ok", True), command=a.command, **out)
    except Refused as e:
        out = dict(ok=False, command=a.command, refused=str(e), **({"hint": e.hint} if e.hint else {}), **e.more)
        code = REFUSED
    except (ScriptError, FileNotFoundError) as e:
        out, code = dict(ok=False, command=a.command, refused=str(e)), REFUSED
    except yaml.YAMLError as e:                              # a file that does not parse: say which, and where
        mark = getattr(e, "problem_mark", None)
        where = f"{mark.name}, line {mark.line + 1}" if mark else "a file"
        out, code = dict(ok=False, command=a.command, refused=f"{where} is not valid YAML: {getattr(e, 'problem', e)}"), REFUSED
    else:
        code = out.pop("exit", OK)
    text = out.pop("text", None)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, default=str))
    elif "refused" in out:
        print("refused: " + out["refused"] + (("\n  " + out["hint"]) if out.get("hint") else ""), file=sys.stderr)
        for p in out.get("introduces", []):
            print("  would introduce: " + p, file=sys.stderr)
    else:
        print(text if text is not None else json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return code
