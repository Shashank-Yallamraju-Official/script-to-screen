"""The `toon` command.

    toon edit <scene>        open the editor on a scene
    toon render <scene>      render a scene (or --episode, --all) to video
    toon ledger [show]       what the audience has had the chance to learn
    toon parity record|check <scene>    has this scene's score, picture or sound changed?
"""
import sys


def main():
    from .presentation import render
    from .readers import ledger, parity
    from .tools import editor
    commands = {"edit": editor.main, "render": render.main, "ledger": ledger.main, "parity": parity.main}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__.strip())
        sys.exit(0 if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help") else 2)
    name = sys.argv.pop(1)
    sys.argv[0] = f"toon {name}"
    commands[name]()


if __name__ == "__main__":
    main()
