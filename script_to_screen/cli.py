"""The `s2s` command (also installed as `script-to-screen`).

    s2s commands             every command, with arguments and an example
    s2s <command> --help     one command's arguments
    s2s edit <scene>         open the tuning editor on a scene

Everything except `edit` is declared in script_to_screen/commands and can answer with --json.
"""
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "edit":       # the editor is a tool for a person, not a command
        from .tools import editor
        sys.argv = ["s2s edit"] + sys.argv[2:]
        return editor.main()
    from . import commands
    sys.exit(commands.run(sys.argv[1:]))


if __name__ == "__main__":
    main()
