"""Command-line entry point — wires the pipeline end-to-end.

Two subcommands:

* ``anonymise FILE [FILE...]`` — anonymises one or more .docx files,
  writing ``<name>_anon.docx`` and an encrypted ``<name>_mapping.dsm``
  next to each input. A single password is reused across all files in
  the batch so they share placeholder numbering (FR-3.2).
* ``rehydrate MAPPING --text FILE`` — restores a redacted LLM output
  using the encrypted mapping.

The CLI exists primarily for development and headless use. The GUI
(M5) calls the same orchestrator function directly.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from .config import Settings
from .core import detector, mapping_store, pipeline
from .core.input_validation import has_error, validate_docx
from .core.placeholder import PlaceholderAllocator
from .core.rehydrate import rehydrate as rehydrate_text
from .logging_setup import write_run


def _anonymise_one(
    path: Path,
    allocator: PlaceholderAllocator,
    cfg: detector.DetectorConfig,
    password: str,
    output_dir: Path | None = None,
    user: str = "",
) -> tuple[Path, Path, int]:
    analysed = pipeline.analyse(path, cfg)
    out_doc, out_map, _ = pipeline.write_output(
        analysed, analysed.detections, allocator, password=password, output_dir=output_dir
    )
    write_run(
        source=path,
        output=out_doc,
        mapping=out_map,
        detections=analysed.detections,
        user=user,
    )
    return out_doc, out_map, len(analysed.detections)


def cmd_anonymise(args: argparse.Namespace) -> int:
    files = [Path(f) for f in args.files]
    for f in files:
        issues = validate_docx(f)
        for issue in issues:
            prefix = "error" if issue.severity == "error" else "warning"
            print(f"{prefix}: {issue.message}", file=sys.stderr)
        if has_error(issues):
            return 2

    settings = Settings.load()
    cfg = detector.DetectorConfig(
        confidence_threshold=args.threshold or settings.confidence_threshold,
        allowlist=settings.allowlist,
        denylist=settings.denylist,
        enabled_types=set(settings.enabled_types) if settings.enabled_types else None,
        detect_dates=settings.detect_dates,
        detect_money=settings.detect_money,
    )

    password = args.password or getpass.getpass("Mapping password: ")
    output_dir = Path(args.output_dir) if args.output_dir else None
    allocator = PlaceholderAllocator()
    user = args.user or getpass.getuser()

    for f in files:
        out_doc, out_map, n = _anonymise_one(
            f, allocator, cfg, password=password, output_dir=output_dir, user=user
        )
        print(f"{f.name}: {n} entities → {out_doc.name}, {out_map.name}")
    return 0


def cmd_rehydrate(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("Mapping password: ")
    mapping = mapping_store.load(args.mapping, password=password)
    text = Path(args.text).read_text(encoding="utf-8") if args.text else sys.stdin.read()
    out = rehydrate_text(text, mapping)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="docshield", description="Offline DOCX PII anonymiser")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("anonymise", help="anonymise one or more .docx files")
    a.add_argument("files", nargs="+", help=".docx file paths")
    a.add_argument("-o", "--output-dir", help="output folder (default: alongside source)")
    a.add_argument("--password", help="mapping password (prompted if omitted)")
    a.add_argument("--threshold", type=float, help="detector confidence threshold")
    a.add_argument("--user", help="user name for the audit log")
    a.set_defaults(func=cmd_anonymise)

    r = sub.add_parser("rehydrate", help="restore real names in an LLM response")
    r.add_argument("mapping", help="path to .dsm mapping file")
    r.add_argument("--text", help="path to text file (default: stdin)")
    r.add_argument("--out", help="output file (default: stdout)")
    r.add_argument("--password", help="mapping password (prompted if omitted)")
    r.set_defaults(func=cmd_rehydrate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
