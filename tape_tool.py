#!/usr/bin/env python3

"""Headless command-line and curses interfaces for Tape File Browser."""

import argparse
import os
import sys
from pathlib import Path

from tape_formats import (
    convert_tape,
    logical_sha256,
    open_tape_image,
    verify_logical_tapes,
)
from tape_text import (
    file_summary_line,
    format_ebcdic,
    format_hex,
    record_header,
    record_summary_line,
    size_summary,
    tape_summary_lines,
)


def _open(path):
    return open_tape_image(str(Path(path).expanduser()))


def _get_file(image, file_number):
    for tape_file in image.files:
        if tape_file.number == file_number:
            return tape_file
    raise ValueError(f"Tape file {file_number} does not exist")


def _get_record(tape_file, record_number):
    for record in tape_file.records:
        if record.number == record_number:
            return record
    raise ValueError(
        f"Record {record_number} does not exist in tape file {tape_file.number}"
    )


def cmd_info(args):
    image = _open(args.image)
    print("\n".join(tape_summary_lines(image)))
    if args.hash:
        print(f"Logical SHA-256: {logical_sha256(image)}")
    return 0


def cmd_files(args):
    image = _open(args.image)
    print(
        f"{os.path.basename(image.path)} — {image.format_name} — "
        f"{len(image.files):,} logical files"
    )
    for tape_file in image.files:
        print(file_summary_line(tape_file))
    return 0


def cmd_records(args):
    image = _open(args.image)
    tape_file = _get_file(image, args.file)
    print(file_summary_line(tape_file))
    print(f"Record sizes: {size_summary(tape_file.sizes)}")
    for record in tape_file.records:
        print(record_summary_line(record))
    return 0


def cmd_show(args):
    image = _open(args.image)
    tape_file = _get_file(image, args.file)
    record = _get_record(tape_file, args.record)
    data = image.read_record(record)

    print(record_header(image, tape_file, record))
    if args.view == "ebcdic":
        print(format_ebcdic(data))
    elif args.view == "hex":
        print(format_hex(data))
    else:
        print("EBCDIC:")
        print(format_ebcdic(data))
        print("\nHEX:")
        print(format_hex(data))
    return 0


def cmd_convert(args):
    report = convert_tape(args.source, args.output)
    print(report.summary())
    print(f"Output: {report.output_path}")
    return 0


def cmd_compare(args):
    first = _open(args.first)
    second = _open(args.second)

    try:
        verify_logical_tapes(first, second)
    except ValueError as exc:
        print(f"Logical tapes differ: {exc}", file=sys.stderr)
        return 1

    first_hash = logical_sha256(first)
    second_hash = logical_sha256(second)

    print(f"First:   {first.path} ({first.format_name})")
    print(f"Second:  {second.path} ({second.format_name})")
    print()
    print(f"Logical files:  {len(first.files):,} = {len(second.files):,}")
    print(f"Tape marks:     {first.tape_mark_count:,} = {second.tape_mark_count:,}")
    print(f"Records:        {first.total_records:,} = {second.total_records:,}")
    print(f"Payload bytes:  {first.total_bytes:,} = {second.total_bytes:,}")
    print(f"Logical SHA-256: {first_hash}")
    print()
    if first_hash == second_hash:
        print("Logical tapes are identical.")
        return 0

    # verify_logical_tapes should make this unreachable, but keep the result
    # explicit in case the logical hash definition is extended later.
    print("Structure and records match, but logical hashes differ.", file=sys.stderr)
    return 1


def _clip(text, width):
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return text[:1]
    return text[: width - 1] + "…"


def _safe_addstr(screen, y, x, text, attr=0):
    height, width = screen.getmaxyx()
    if y < 0 or y >= height or x < 0 or x >= width:
        return
    available = width - x
    if available <= 0:
        return
    try:
        screen.addstr(y, x, _clip(str(text), available), attr)
    except Exception:
        # Curses may reject a write to the final cell on some terminals.
        pass


def _draw_list(screen, title, items, selected, x, y, width, height, focused):
    import curses

    heading_attr = curses.A_BOLD | (curses.A_REVERSE if focused else 0)
    _safe_addstr(screen, y, x, title.ljust(max(0, width - 1)), heading_attr)

    visible = max(0, height - 1)
    if visible == 0:
        return

    if not items:
        _safe_addstr(screen, y + 1, x, "(empty)", curses.A_DIM)
        return

    selected = max(0, min(selected, len(items) - 1))
    start = max(0, selected - visible // 2)
    start = min(start, max(0, len(items) - visible))

    for row, item_index in enumerate(range(start, min(len(items), start + visible))):
        prefix = "> " if item_index == selected else "  "
        attr = curses.A_REVERSE if item_index == selected else 0
        _safe_addstr(
            screen,
            y + 1 + row,
            x,
            _clip(prefix + items[item_index], width - 1),
            attr,
        )


def _viewer_lines(image, tape_file, record, mode):
    if record is None:
        return [
            file_summary_line(tape_file),
            f"Record sizes: {size_summary(tape_file.sizes)}",
            "",
            "This logical tape file contains no records.",
        ]

    data = image.read_record(record)
    lines = record_header(image, tape_file, record).splitlines()
    lines.append("")

    if mode == "EBCDIC":
        lines.extend(format_ebcdic(data).splitlines())
    elif mode == "HEX":
        lines.extend(format_hex(data).splitlines())
    else:
        lines.append("EBCDIC:")
        lines.extend(format_ebcdic(data).splitlines())
        lines.extend(["", "HEX:"])
        lines.extend(format_hex(data).splitlines())
    return lines


def _browse(stdscr, image):
    import curses

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)

    file_index = 0
    record_index = 0
    focus = 0
    view_modes = ("EBCDIC", "HEX", "BOTH")
    view_index = 0
    viewer_scroll = 0

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        if height < 16 or width < 72:
            _safe_addstr(
                stdscr,
                0,
                0,
                f"Terminal too small ({width}x{height}); need at least 72x16.",
                curses.A_BOLD,
            )
            _safe_addstr(stdscr, 2, 0, "Resize the terminal, or press q to quit.")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
            continue

        file_w = max(22, min(34, width // 4))
        record_w = max(28, min(42, width // 3))
        viewer_x = file_w + record_w + 2
        viewer_w = width - viewer_x
        body_y = 2
        body_h = height - 4

        title = (
            f"Tape File Browser — {os.path.basename(image.path)} — "
            f"{image.format_name} — {image.total_records:,} records — "
            f"{image.tape_mark_count:,} tape marks"
        )
        _safe_addstr(stdscr, 0, 0, title, curses.A_BOLD)

        for y in range(1, height - 1):
            _safe_addstr(stdscr, y, file_w, "│", curses.A_DIM)
            _safe_addstr(stdscr, y, file_w + record_w + 1, "│", curses.A_DIM)

        file_items = [
            f"{f.number}: {len(f.records):,} rec / {f.total_bytes:,} B"
            for f in image.files
        ]

        if image.files:
            file_index = max(0, min(file_index, len(image.files) - 1))
            tape_file = image.files[file_index]
            record_items = [
                f"{r.number}: {r.length:,} B @ 0x{r.image_offset:X}"
                + (" ERROR" if r.error else "")
                for r in tape_file.records
            ]
            if tape_file.records:
                record_index = max(0, min(record_index, len(tape_file.records) - 1))
                record = tape_file.records[record_index]
            else:
                record_index = 0
                record = None
        else:
            tape_file = None
            record_items = []
            record = None

        _draw_list(
            stdscr,
            " Tape files ",
            file_items,
            file_index,
            0,
            body_y,
            file_w,
            body_h,
            focus == 0,
        )
        _draw_list(
            stdscr,
            " Records ",
            record_items,
            record_index,
            file_w + 1,
            body_y,
            record_w,
            body_h,
            focus == 1,
        )

        mode = view_modes[view_index]
        viewer_heading = f" Record view [{mode}] "
        heading_attr = curses.A_BOLD | (curses.A_REVERSE if focus == 2 else 0)
        _safe_addstr(
            stdscr,
            body_y,
            viewer_x,
            viewer_heading.ljust(max(0, viewer_w - 1)),
            heading_attr,
        )

        if tape_file is None:
            viewer_lines = ["No logical tape files in this image."]
        else:
            viewer_lines = _viewer_lines(image, tape_file, record, mode)

        viewer_visible = max(1, body_h - 1)
        max_scroll = max(0, len(viewer_lines) - viewer_visible)
        viewer_scroll = max(0, min(viewer_scroll, max_scroll))
        for row, line in enumerate(
            viewer_lines[viewer_scroll : viewer_scroll + viewer_visible]
        ):
            _safe_addstr(stdscr, body_y + 1 + row, viewer_x, line)

        help_text = (
            "←/→ or Tab: pane  ↑/↓: move/scroll  PgUp/PgDn: page  "
            "v: view  e: EBCDIC  x: hex  b: both  q: quit"
        )
        _safe_addstr(stdscr, height - 1, 0, help_text, curses.A_REVERSE)
        stdscr.refresh()

        key = stdscr.getch()

        if key in (ord("q"), ord("Q"), 27):
            return
        if key in (9,):
            focus = (focus + 1) % 3
            continue
        if key == curses.KEY_LEFT:
            focus = max(0, focus - 1)
            continue
        if key == curses.KEY_RIGHT:
            focus = min(2, focus + 1)
            continue
        if key in (ord("v"), ord("V")):
            view_index = (view_index + 1) % len(view_modes)
            viewer_scroll = 0
            continue
        if key in (ord("e"), ord("E")):
            view_index = 0
            viewer_scroll = 0
            continue
        if key in (ord("x"), ord("X")):
            view_index = 1
            viewer_scroll = 0
            continue
        if key in (ord("b"), ord("B")):
            view_index = 2
            viewer_scroll = 0
            continue

        if focus == 0 and image.files:
            old = file_index
            if key == curses.KEY_UP:
                file_index = max(0, file_index - 1)
            elif key == curses.KEY_DOWN:
                file_index = min(len(image.files) - 1, file_index + 1)
            elif key == curses.KEY_PPAGE:
                file_index = max(0, file_index - max(1, body_h - 2))
            elif key == curses.KEY_NPAGE:
                file_index = min(
                    len(image.files) - 1, file_index + max(1, body_h - 2)
                )
            elif key == curses.KEY_HOME:
                file_index = 0
            elif key == curses.KEY_END:
                file_index = len(image.files) - 1
            if file_index != old:
                record_index = 0
                viewer_scroll = 0

        elif focus == 1 and tape_file and tape_file.records:
            old = record_index
            if key == curses.KEY_UP:
                record_index = max(0, record_index - 1)
            elif key == curses.KEY_DOWN:
                record_index = min(len(tape_file.records) - 1, record_index + 1)
            elif key == curses.KEY_PPAGE:
                record_index = max(0, record_index - max(1, body_h - 2))
            elif key == curses.KEY_NPAGE:
                record_index = min(
                    len(tape_file.records) - 1,
                    record_index + max(1, body_h - 2),
                )
            elif key == curses.KEY_HOME:
                record_index = 0
            elif key == curses.KEY_END:
                record_index = len(tape_file.records) - 1
            if record_index != old:
                viewer_scroll = 0

        elif focus == 2:
            if key == curses.KEY_UP:
                viewer_scroll = max(0, viewer_scroll - 1)
            elif key == curses.KEY_DOWN:
                viewer_scroll = min(max_scroll, viewer_scroll + 1)
            elif key == curses.KEY_PPAGE:
                viewer_scroll = max(0, viewer_scroll - viewer_visible)
            elif key == curses.KEY_NPAGE:
                viewer_scroll = min(max_scroll, viewer_scroll + viewer_visible)
            elif key == curses.KEY_HOME:
                viewer_scroll = 0
            elif key == curses.KEY_END:
                viewer_scroll = max_scroll


def cmd_browse(args):
    image = _open(args.image)
    try:
        import curses
    except ImportError as exc:
        raise RuntimeError(
            "The curses module is not available in this Python installation"
        ) from exc

    curses.wrapper(_browse, image)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tape-tool",
        description=(
            "Headless tools for browsing, inspecting, comparing, and converting "
            "SIMH/AWS tape images."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="show tape image summary")
    info.add_argument("image")
    info.add_argument(
        "--hash",
        action="store_true",
        help="also calculate the container-independent logical SHA-256",
    )
    info.set_defaults(func=cmd_info)

    files = subparsers.add_parser("files", help="list logical tape files")
    files.add_argument("image")
    files.set_defaults(func=cmd_files)

    records = subparsers.add_parser("records", help="list records in a tape file")
    records.add_argument("image")
    records.add_argument("--file", type=int, required=True, help="logical file number")
    records.set_defaults(func=cmd_records)

    show = subparsers.add_parser("show", help="display one record")
    show.add_argument("image")
    show.add_argument("--file", type=int, required=True, help="logical file number")
    show.add_argument("--record", type=int, required=True, help="record number")
    show.add_argument(
        "--view",
        choices=("ebcdic", "hex", "both"),
        default="ebcdic",
        help="record display format (default: ebcdic)",
    )
    show.set_defaults(func=cmd_show)

    convert = subparsers.add_parser(
        "convert", help="convert SIMH <-> AWS and verify the result"
    )
    convert.add_argument("source")
    convert.add_argument("output")
    convert.set_defaults(func=cmd_convert)

    compare = subparsers.add_parser(
        "compare", help="compare two tape images by logical files and payloads"
    )
    compare.add_argument("first")
    compare.add_argument("second")
    compare.set_defaults(func=cmd_compare)

    browse = subparsers.add_parser(
        "browse", help="interactive curses browser; no X/GTK required"
    )
    browse.add_argument("image")
    browse.set_defaults(func=cmd_browse)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"tape-tool: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
