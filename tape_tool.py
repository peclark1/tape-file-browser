#!/usr/bin/env python3

"""Command-line and curses TUI interfaces for Tape File Browser."""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from tape_formats import (
    TapeImage,
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

TAPE_SUFFIXES = {".tap", ".aws", ".awstape"}


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


def _comparison_lines(images):
    reference = images[0]
    reference_hash = logical_sha256(reference)
    lines = [
        f"Reference: {reference.path} ({reference.format_name})",
        f"Logical SHA-256: {reference_hash}",
        "",
    ]
    all_match = True

    for candidate in images[1:]:
        try:
            verify_logical_tapes(reference, candidate)
            candidate_hash = logical_sha256(candidate)
            if candidate_hash != reference_hash:
                all_match = False
                lines.append(
                    f"DIFFERENT  {candidate.path} — logical SHA-256 differs"
                )
            else:
                lines.append(f"IDENTICAL  {candidate.path} ({candidate.format_name})")
        except ValueError as exc:
            all_match = False
            lines.append(f"DIFFERENT  {candidate.path}")
            lines.append(f"           {exc}")

    lines.extend(
        [
            "",
            (
                "All selected tape images are logically identical."
                if all_match
                else "One or more selected tape images differ from the reference."
            ),
        ]
    )
    return lines, all_match


def cmd_compare(args):
    if len(args.images) < 2:
        raise ValueError("compare requires at least two tape images")
    images = [_open(path) for path in args.images]
    lines, all_match = _comparison_lines(images)
    print("\n".join(lines))
    return 0 if all_match else 1


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


def _list_start(count, selected, visible):
    if count <= 0 or visible <= 0:
        return 0
    selected = max(0, min(selected, count - 1))
    start = max(0, selected - visible // 2)
    return min(start, max(0, count - visible))


def _draw_list(screen, title, items, selected, x, y, width, height, focused):
    import curses

    heading_attr = curses.A_BOLD | (curses.A_REVERSE if focused else 0)
    _safe_addstr(screen, y, x, title.ljust(max(0, width - 1)), heading_attr)

    visible = max(0, height - 1)
    if visible == 0:
        return 0

    if not items:
        _safe_addstr(screen, y + 1, x, "(empty)", curses.A_DIM)
        return 0

    selected = max(0, min(selected, len(items) - 1))
    start = _list_start(len(items), selected, visible)

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
    return start


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


@dataclass
class OpenTapeState:
    image: TapeImage
    file_index: int = 0
    record_index: int = 0
    viewer_scroll: int = 0
    compare_selected: bool = False


def _normalized_path(path):
    return os.path.realpath(os.path.abspath(os.path.expanduser(str(path))))


def _add_open_images(states, paths):
    existing = {_normalized_path(state.image.path) for state in states}
    added = []
    errors = []

    for path in paths:
        normalized = _normalized_path(path)
        if normalized in existing:
            continue
        try:
            image = _open(normalized)
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        states.append(OpenTapeState(image=image))
        existing.add(normalized)
        added.append(normalized)

    return added, errors


def _picker_entries(directory):
    directories = []
    files = []
    try:
        entries = list(Path(directory).iterdir())
    except OSError:
        return []

    for entry in entries:
        try:
            if entry.is_dir():
                if not entry.name.startswith("."):
                    directories.append(entry)
            elif entry.is_file() and entry.suffix.lower() in TAPE_SUFFIXES:
                files.append(entry)
        except OSError:
            continue

    directories.sort(key=lambda item: item.name.lower())
    files.sort(key=lambda item: item.name.lower())
    return [(entry, True) for entry in directories] + [
        (entry, False) for entry in files
    ]


def _file_picker(stdscr, start_dir):
    """Curses file-open dialog with multi-select support."""
    import curses

    directory = Path(start_dir).expanduser()
    if not directory.is_dir():
        directory = Path.cwd()
    directory = directory.resolve()

    selected = 0
    marked = set()
    status = ""

    while True:
        entries = _picker_entries(directory)
        if entries:
            selected = max(0, min(selected, len(entries) - 1))
        else:
            selected = 0

        stdscr.erase()
        height, width = stdscr.getmaxyx()

        title = " Open tape image(s) "
        _safe_addstr(stdscr, 0, 0, title, curses.A_BOLD | curses.A_REVERSE)
        _safe_addstr(stdscr, 1, 0, f"Directory: {directory}", curses.A_BOLD)

        list_y = 3
        visible = max(1, height - 7)
        start = _list_start(len(entries), selected, visible)

        if not entries:
            _safe_addstr(stdscr, list_y, 2, "(no tape images or subdirectories)")
        else:
            for row, idx in enumerate(range(start, min(len(entries), start + visible))):
                path, is_dir = entries[idx]
                if is_dir:
                    label = f"    <DIR> {path.name}/"
                else:
                    check = "x" if _normalized_path(path) in marked else " "
                    label = f"[{check}]       {path.name}"
                attr = curses.A_REVERSE if idx == selected else 0
                _safe_addstr(stdscr, list_y + row, 0, label, attr)

        _safe_addstr(
            stdscr,
            height - 3,
            0,
            status or f"{len(marked)} file(s) marked",
            curses.A_DIM,
        )
        _safe_addstr(
            stdscr,
            height - 2,
            0,
            "Space: mark  Enter: open current/marked  Backspace: parent",
        )
        _safe_addstr(
            stdscr,
            height - 1,
            0,
            "↑/↓ PgUp/PgDn Home/End: navigate   Esc/q: cancel",
            curses.A_REVERSE,
        )
        stdscr.refresh()

        key = stdscr.getch()

        if key in (27, ord("q"), ord("Q")):
            return []
        if key in (curses.KEY_BACKSPACE, 127, 8):
            parent = directory.parent
            if parent != directory:
                directory = parent
                selected = 0
                marked.clear()
                status = ""
            continue
        if key == curses.KEY_UP:
            selected = max(0, selected - 1)
            continue
        if key == curses.KEY_DOWN:
            selected = min(max(0, len(entries) - 1), selected + 1)
            continue
        if key == curses.KEY_PPAGE:
            selected = max(0, selected - visible)
            continue
        if key == curses.KEY_NPAGE:
            selected = min(max(0, len(entries) - 1), selected + visible)
            continue
        if key == curses.KEY_HOME:
            selected = 0
            continue
        if key == curses.KEY_END:
            selected = max(0, len(entries) - 1)
            continue

        if not entries:
            continue

        path, is_dir = entries[selected]

        if key == ord(" "):
            if is_dir:
                status = "Directories cannot be marked; press Enter to open it."
            else:
                normalized = _normalized_path(path)
                if normalized in marked:
                    marked.remove(normalized)
                else:
                    marked.add(normalized)
                status = ""
            continue

        if key in (10, 13, curses.KEY_ENTER):
            if is_dir:
                directory = path.resolve()
                selected = 0
                marked.clear()
                status = ""
                continue

            if marked:
                return sorted(marked)
            return [_normalized_path(path)]


def _comparison_view(states):
    selected = [state.image for state in states if state.compare_selected]
    if len(selected) < 2:
        return [
            "Compare",
            "",
            "Select at least two open tape images in the Images pane.",
            "Press Space to mark or unmark an image for comparison.",
            "Then press c.",
        ], False

    return _comparison_lines(selected)


def _browse(stdscr, initial_states):
    import curses

    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)

    try:
        curses.mousemask(curses.ALL_MOUSE_EVENTS)
    except curses.error:
        pass

    states = list(initial_states)
    image_index = 0
    focus = 0
    view_modes = ("EBCDIC", "HEX", "BOTH")
    view_index = 0
    compare_lines = None
    status = ""

    if states:
        picker_dir = Path(states[0].image.path).parent
    else:
        picker_dir = Path.cwd()
        chosen = _file_picker(stdscr, picker_dir)
        added, errors = _add_open_images(states, chosen)
        if added:
            picker_dir = Path(added[-1]).parent
        if errors:
            status = errors[0]

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()

        if height < 16 or width < 100:
            _safe_addstr(
                stdscr,
                0,
                0,
                f"Terminal too small ({width}x{height}); need at least 100x16.",
                curses.A_BOLD,
            )
            _safe_addstr(stdscr, 2, 0, "Resize the terminal, or press q to quit.")
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
            continue

        image_w = max(20, min(30, width // 5))
        file_w = max(18, min(28, width // 5))
        record_w = max(24, min(36, width // 4))
        file_x = image_w + 1
        record_x = file_x + file_w + 1
        viewer_x = record_x + record_w + 1
        viewer_w = width - viewer_x
        body_y = 2
        body_h = height - 5

        if states:
            image_index = max(0, min(image_index, len(states) - 1))
            current_state = states[image_index]
            image = current_state.image
            if image.files:
                current_state.file_index = max(
                    0, min(current_state.file_index, len(image.files) - 1)
                )
                tape_file = image.files[current_state.file_index]
                if tape_file.records:
                    current_state.record_index = max(
                        0,
                        min(current_state.record_index, len(tape_file.records) - 1),
                    )
                    record = tape_file.records[current_state.record_index]
                else:
                    current_state.record_index = 0
                    record = None
            else:
                tape_file = None
                record = None
        else:
            current_state = None
            image = None
            tape_file = None
            record = None

        title = f"Tape File Browser TUI — {len(states)} image(s) open"
        if image is not None:
            title += (
                f" — {os.path.basename(image.path)} [{image.format_name}]"
                f" — {image.total_records:,} records"
            )
        _safe_addstr(stdscr, 0, 0, title, curses.A_BOLD)

        for y in range(1, height - 2):
            _safe_addstr(stdscr, y, image_w, "│", curses.A_DIM)
            _safe_addstr(stdscr, y, file_x + file_w, "│", curses.A_DIM)
            _safe_addstr(stdscr, y, record_x + record_w, "│", curses.A_DIM)

        image_items = []
        for state in states:
            check = "x" if state.compare_selected else " "
            name = os.path.basename(state.image.path)
            image_items.append(f"[{check}] {name} [{state.image.format_name}]")

        if image is not None:
            file_items = [
                f"{f.number}: {len(f.records):,} rec / {f.total_bytes:,} B"
                for f in image.files
            ]
        else:
            file_items = []

        if tape_file is not None:
            record_items = [
                f"{r.number}: {r.length:,} B @ 0x{r.image_offset:X}"
                + (" ERROR" if r.error else "")
                for r in tape_file.records
            ]
        else:
            record_items = []

        image_start = _draw_list(
            stdscr,
            " Images ",
            image_items,
            image_index,
            0,
            body_y,
            image_w,
            body_h,
            focus == 0,
        )
        file_start = _draw_list(
            stdscr,
            " Tape files ",
            file_items,
            current_state.file_index if current_state else 0,
            file_x,
            body_y,
            file_w,
            body_h,
            focus == 1,
        )
        record_start = _draw_list(
            stdscr,
            " Records ",
            record_items,
            current_state.record_index if current_state else 0,
            record_x,
            body_y,
            record_w,
            body_h,
            focus == 2,
        )

        mode = view_modes[view_index]
        viewer_heading = (
            " Compare results "
            if compare_lines is not None
            else f" Record view [{mode}] "
        )
        heading_attr = curses.A_BOLD | (curses.A_REVERSE if focus == 3 else 0)
        _safe_addstr(
            stdscr,
            body_y,
            viewer_x,
            viewer_heading.ljust(max(0, viewer_w - 1)),
            heading_attr,
        )

        if compare_lines is not None:
            viewer_lines = compare_lines
        elif image is None:
            viewer_lines = [
                "No tape images are open.",
                "",
                "Press o to open one or more SIMH/AWS tape images.",
            ]
        elif tape_file is None:
            viewer_lines = ["No logical tape files in this image."]
        else:
            viewer_lines = _viewer_lines(image, tape_file, record, mode)

        viewer_visible = max(1, body_h - 1)
        viewer_scroll = current_state.viewer_scroll if current_state else 0
        max_scroll = max(0, len(viewer_lines) - viewer_visible)
        viewer_scroll = max(0, min(viewer_scroll, max_scroll))
        if current_state:
            current_state.viewer_scroll = viewer_scroll

        for row, line in enumerate(
            viewer_lines[viewer_scroll : viewer_scroll + viewer_visible]
        ):
            _safe_addstr(stdscr, body_y + 1 + row, viewer_x, line)

        selected_count = sum(1 for state in states if state.compare_selected)
        status_line = status or (
            f"{selected_count} image(s) marked for compare"
            if selected_count
            else "Space marks images for compare"
        )
        _safe_addstr(stdscr, height - 2, 0, status_line, curses.A_DIM)

        help_text = (
            "o: open  Space: mark  c: compare  Del: close  "
            "←/→/Tab: pane  ↑/↓: move  v/e/x/b: view  q: quit"
        )
        _safe_addstr(stdscr, height - 1, 0, help_text, curses.A_REVERSE)
        stdscr.refresh()

        key = stdscr.getch()
        status = ""

        if key in (ord("q"), ord("Q")):
            return

        if key in (ord("o"), ord("O")):
            chosen = _file_picker(stdscr, picker_dir)
            if chosen:
                added, errors = _add_open_images(states, chosen)
                if added:
                    picker_dir = Path(added[-1]).parent
                    image_index = len(states) - 1
                    compare_lines = None
                if errors:
                    status = errors[0]
            continue

        if key == curses.KEY_MOUSE:
            try:
                _id, mx, my, _z, bstate = curses.getmouse()
            except curses.error:
                continue

            click_mask = (
                getattr(curses, "BUTTON1_CLICKED", 0)
                | getattr(curses, "BUTTON1_PRESSED", 0)
                | getattr(curses, "BUTTON1_RELEASED", 0)
            )
            if not (bstate & click_mask):
                continue

            row = my - (body_y + 1)
            if mx < image_w:
                focus = 0
                if 0 <= row < body_h - 1:
                    idx = image_start + row
                    if idx < len(states):
                        image_index = idx
                        compare_lines = None
            elif file_x <= mx < file_x + file_w:
                focus = 1
                if current_state and 0 <= row < body_h - 1:
                    idx = file_start + row
                    if idx < len(current_state.image.files):
                        current_state.file_index = idx
                        current_state.record_index = 0
                        current_state.viewer_scroll = 0
                        compare_lines = None
            elif record_x <= mx < record_x + record_w:
                focus = 2
                if tape_file and current_state and 0 <= row < body_h - 1:
                    idx = record_start + row
                    if idx < len(tape_file.records):
                        current_state.record_index = idx
                        current_state.viewer_scroll = 0
                        compare_lines = None
            elif mx >= viewer_x:
                focus = 3
            continue

        if key in (9,):
            focus = (focus + 1) % 4
            continue
        if key == curses.KEY_LEFT:
            focus = max(0, focus - 1)
            continue
        if key == curses.KEY_RIGHT:
            focus = min(3, focus + 1)
            continue

        if key == ord(" ") and focus == 0 and current_state:
            current_state.compare_selected = not current_state.compare_selected
            continue

        if key in (ord("c"), ord("C")):
            compare_lines, _ = _comparison_view(states)
            if current_state:
                current_state.viewer_scroll = 0
            focus = 3
            continue

        if key in (curses.KEY_DC, 127) and focus == 0 and states:
            removed = states.pop(image_index)
            status = f"Closed {os.path.basename(removed.image.path)}"
            image_index = min(image_index, max(0, len(states) - 1))
            compare_lines = None
            continue

        if key in (ord("v"), ord("V")):
            view_index = (view_index + 1) % len(view_modes)
            compare_lines = None
            if current_state:
                current_state.viewer_scroll = 0
            continue
        if key in (ord("e"), ord("E")):
            view_index = 0
            compare_lines = None
            if current_state:
                current_state.viewer_scroll = 0
            continue
        if key in (ord("x"), ord("X")):
            view_index = 1
            compare_lines = None
            if current_state:
                current_state.viewer_scroll = 0
            continue
        if key in (ord("b"), ord("B")):
            view_index = 2
            compare_lines = None
            if current_state:
                current_state.viewer_scroll = 0
            continue

        page = max(1, body_h - 2)

        if focus == 0 and states:
            old = image_index
            if key == curses.KEY_UP:
                image_index = max(0, image_index - 1)
            elif key == curses.KEY_DOWN:
                image_index = min(len(states) - 1, image_index + 1)
            elif key == curses.KEY_PPAGE:
                image_index = max(0, image_index - page)
            elif key == curses.KEY_NPAGE:
                image_index = min(len(states) - 1, image_index + page)
            elif key == curses.KEY_HOME:
                image_index = 0
            elif key == curses.KEY_END:
                image_index = len(states) - 1
            if image_index != old:
                compare_lines = None

        elif focus == 1 and current_state and image and image.files:
            old = current_state.file_index
            if key == curses.KEY_UP:
                current_state.file_index = max(0, current_state.file_index - 1)
            elif key == curses.KEY_DOWN:
                current_state.file_index = min(
                    len(image.files) - 1, current_state.file_index + 1
                )
            elif key == curses.KEY_PPAGE:
                current_state.file_index = max(0, current_state.file_index - page)
            elif key == curses.KEY_NPAGE:
                current_state.file_index = min(
                    len(image.files) - 1, current_state.file_index + page
                )
            elif key == curses.KEY_HOME:
                current_state.file_index = 0
            elif key == curses.KEY_END:
                current_state.file_index = len(image.files) - 1
            if current_state.file_index != old:
                current_state.record_index = 0
                current_state.viewer_scroll = 0
                compare_lines = None

        elif focus == 2 and current_state and tape_file and tape_file.records:
            old = current_state.record_index
            if key == curses.KEY_UP:
                current_state.record_index = max(0, current_state.record_index - 1)
            elif key == curses.KEY_DOWN:
                current_state.record_index = min(
                    len(tape_file.records) - 1, current_state.record_index + 1
                )
            elif key == curses.KEY_PPAGE:
                current_state.record_index = max(
                    0, current_state.record_index - page
                )
            elif key == curses.KEY_NPAGE:
                current_state.record_index = min(
                    len(tape_file.records) - 1,
                    current_state.record_index + page,
                )
            elif key == curses.KEY_HOME:
                current_state.record_index = 0
            elif key == curses.KEY_END:
                current_state.record_index = len(tape_file.records) - 1
            if current_state.record_index != old:
                current_state.viewer_scroll = 0
                compare_lines = None

        elif focus == 3 and current_state:
            if key == curses.KEY_UP:
                current_state.viewer_scroll = max(
                    0, current_state.viewer_scroll - 1
                )
            elif key == curses.KEY_DOWN:
                current_state.viewer_scroll = min(
                    max_scroll, current_state.viewer_scroll + 1
                )
            elif key == curses.KEY_PPAGE:
                current_state.viewer_scroll = max(
                    0, current_state.viewer_scroll - viewer_visible
                )
            elif key == curses.KEY_NPAGE:
                current_state.viewer_scroll = min(
                    max_scroll, current_state.viewer_scroll + viewer_visible
                )
            elif key == curses.KEY_HOME:
                current_state.viewer_scroll = 0
            elif key == curses.KEY_END:
                current_state.viewer_scroll = max_scroll


def cmd_browse(args):
    states = []
    added, errors = _add_open_images(states, args.images)
    if errors and not added and args.images:
        for error in errors:
            print(f"tape-tool: {error}", file=sys.stderr)
        return 1

    try:
        import curses
    except ImportError as exc:
        raise RuntimeError(
            "The curses module is not available in this Python installation"
        ) from exc

    curses.wrapper(_browse, states)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="tape-tool",
        description=(
            "Command-line and text-mode tools for browsing, inspecting, comparing, "
            "and converting SIMH/AWS tape images."
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
        "compare",
        help="compare two or more tape images against the first image",
    )
    compare.add_argument("images", nargs="+")
    compare.set_defaults(func=cmd_compare)

    browse = subparsers.add_parser(
        "browse",
        help="interactive curses TUI; accepts zero or more initial images",
    )
    browse.add_argument("images", nargs="*")
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
