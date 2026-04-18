"""PyInstaller entry script.

Kept outside the ``docshield`` package so PyInstaller picks it up as the
top-level script *and* ``docshield`` still resolves as an installed
package (the spec's ``pathex`` adds ``src/`` to ``sys.path``). This sidesteps
``attempted relative import with no known parent package`` when the
frozen binary boots.
"""

from docshield.app import main

if __name__ == "__main__":
    raise SystemExit(main())
