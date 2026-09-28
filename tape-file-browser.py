#!/usr/bin/env python3

import argparse
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from tape_formats import (
    ConversionReport,
    TapeImage,
    convert_tape,
    logical_sha256,
    open_tape_image,
    verify_logical_tapes,
)
from tape_text import format_ebcdic, size_summary

APP_ID = "com.peclark.TapeFileBrowser"


@dataclass
class OpenImageState:
    image: TapeImage
    file_index: int = 0
    record_index: int = 0
    compare_selected: bool = False


class TapeBrowserWindow(Gtk.ApplicationWindow):
    def __init__(self, app, initial_paths=None):
        super().__init__(application=app)
        self.set_title("Tape File Browser")
        self.set_default_size(1280, 800)

        self.open_images: list[OpenImageState] = []
        self.active_image_index: int | None = None
        self.tap: TapeImage | None = None
        self.initial_paths = list(initial_paths or [])
        self._file_dialog = None
        self._convert_dialog = None
        self._restoring_selection = False

        self._build_ui()

        if self.initial_paths:
            GLib.idle_add(self.load_tapes, self.initial_paths)

    def _build_ui(self):
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        self.open_button = Gtk.Button(label="Open…")
        self.open_button.set_icon_name("document-open-symbolic")
        self.open_button.connect("clicked", self.on_open_clicked)
        header.pack_start(self.open_button)

        self.close_button = Gtk.Button(label="Close")
        self.close_button.set_icon_name("window-close-symbolic")
        self.close_button.set_sensitive(False)
        self.close_button.connect("clicked", self.on_close_clicked)
        header.pack_start(self.close_button)

        self.convert_button = Gtk.Button(label="Convert…")
        self.convert_button.set_icon_name("document-save-as-symbolic")
        self.convert_button.set_sensitive(False)
        self.convert_button.connect("clicked", self.on_convert_clicked)
        header.pack_start(self.convert_button)

        self.compare_button = Gtk.Button(label="Compare")
        self.compare_button.set_icon_name("view-compare-symbolic")
        self.compare_button.set_sensitive(False)
        self.compare_button.connect("clicked", self.on_compare_clicked)
        header.pack_start(self.compare_button)

        self.spinner = Gtk.Spinner()
        header.pack_end(self.spinner)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        # Like the TUI, navigation lives across the top and wide content uses
        # the full-width lower pane.
        self.main_pane = Gtk.Paned.new(Gtk.Orientation.VERTICAL)
        self.main_pane.set_position(330)
        self.main_pane.set_wide_handle(True)
        self.main_pane.set_vexpand(True)
        outer.append(self.main_pane)

        top_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        top_pane.set_position(330)
        top_pane.set_wide_handle(True)
        self.main_pane.set_start_child(top_pane)
        self.main_pane.set_resize_start_child(True)
        self.main_pane.set_shrink_start_child(False)

        image_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        image_box.set_margin_top(8)
        image_box.set_margin_bottom(8)
        image_box.set_margin_start(8)
        image_box.set_margin_end(4)

        image_heading = Gtk.Label(label="Images", xalign=0)
        image_heading.add_css_class("heading")
        image_box.append(image_heading)

        self.image_list = Gtk.ListBox()
        self.image_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.image_list.connect("row-selected", self.on_image_selected)

        image_scroll = Gtk.ScrolledWindow()
        image_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        image_scroll.set_vexpand(True)
        image_scroll.set_child(self.image_list)
        image_box.append(image_scroll)

        compare_hint = Gtk.Label(
            label="Check two or more images to compare", xalign=0
        )
        compare_hint.add_css_class("dim-label")
        image_box.append(compare_hint)

        top_pane.set_start_child(image_box)
        top_pane.set_resize_start_child(False)
        top_pane.set_shrink_start_child(False)

        nav_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        nav_pane.set_position(390)
        nav_pane.set_wide_handle(True)
        top_pane.set_end_child(nav_pane)

        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        file_box.set_margin_top(8)
        file_box.set_margin_bottom(8)
        file_box.set_margin_start(4)
        file_box.set_margin_end(4)

        file_heading = Gtk.Label(label="Tape files", xalign=0)
        file_heading.add_css_class("heading")
        file_box.append(file_heading)

        self.file_strings = Gtk.StringList.new([])
        self.file_selection = Gtk.SingleSelection.new(self.file_strings)
        self.file_selection.set_autoselect(False)
        self.file_selection.set_can_unselect(True)
        self.file_factory = self._make_string_factory()
        self.file_view = Gtk.ListView(
            model=self.file_selection, factory=self.file_factory
        )
        self.file_view.set_single_click_activate(False)
        self.file_selection.connect("notify::selected", self.on_file_selected)

        file_scroll = Gtk.ScrolledWindow()
        file_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        file_scroll.set_vexpand(True)
        file_scroll.set_child(self.file_view)
        file_box.append(file_scroll)
        nav_pane.set_start_child(file_box)
        nav_pane.set_resize_start_child(True)
        nav_pane.set_shrink_start_child(False)

        record_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        record_box.set_margin_top(8)
        record_box.set_margin_bottom(8)
        record_box.set_margin_start(4)
        record_box.set_margin_end(8)

        self.record_heading = Gtk.Label(label="Records", xalign=0)
        self.record_heading.add_css_class("heading")
        record_box.append(self.record_heading)

        self.record_strings = Gtk.StringList.new([])
        self.record_selection = Gtk.SingleSelection.new(self.record_strings)
        self.record_selection.set_autoselect(False)
        self.record_selection.set_can_unselect(True)
        self.record_factory = self._make_string_factory()
        self.record_view = Gtk.ListView(
            model=self.record_selection, factory=self.record_factory
        )
        self.record_selection.connect(
            "notify::selected", self.on_record_selected
        )

        record_scroll = Gtk.ScrolledWindow()
        record_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        record_scroll.set_vexpand(True)
        record_scroll.set_child(self.record_view)
        record_box.append(record_scroll)
        nav_pane.set_end_child(record_box)
        nav_pane.set_resize_end_child(True)
        nav_pane.set_shrink_end_child(False)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        text_box.set_margin_top(6)
        text_box.set_margin_bottom(8)
        text_box.set_margin_start(8)
        text_box.set_margin_end(8)

        self.record_title = Gtk.Label(label="Record view", xalign=0)
        self.record_title.add_css_class("heading")
        text_box.append(self.record_title)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text_buffer = self.text_view.get_buffer()
        self.text_buffer.set_text(
            "Open one or more SIMH .tap or AWS .aws images. "
            "Select an image, tape file, and record to browse its contents."
        )

        self.text_scroll = Gtk.ScrolledWindow()
        self.text_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self.text_scroll.set_hexpand(True)
        self.text_scroll.set_vexpand(True)
        self.text_scroll.set_child(self.text_view)
        text_box.append(self.text_scroll)

        self.main_pane.set_end_child(text_box)
        self.main_pane.set_resize_end_child(True)
        self.main_pane.set_shrink_end_child(False)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        outer.append(separator)

        self.status = Gtk.Label(label="No tape images loaded", xalign=0)
        self.status.set_margin_top(5)
        self.status.set_margin_bottom(5)
        self.status.set_margin_start(8)
        self.status.set_margin_end(8)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(self.status)

    def _set_view_text(self, text, title=None):
        """Replace lower-pane text and force a full viewport repaint.

        GTK4 can occasionally leave stale glyph fragments behind when a large
        TextView buffer is replaced by much shorter content.  Updating the
        buffer is correct, but explicitly invalidating the lower viewport on
        the next main-loop turn prevents those old snapshots from lingering.
        """
        if title is not None:
            self.record_title.set_text(title)
        self.text_buffer.set_text(text)
        GLib.idle_add(self._refresh_text_view)
    
    def _refresh_text_view(self):
        if not self.get_mapped():
            return False

        vadjustment = self.text_scroll.get_vadjustment()
        hadjustment = self.text_scroll.get_hadjustment()
        if vadjustment is not None:
            vadjustment.set_value(vadjustment.get_lower())
        if hadjustment is not None:
            hadjustment.set_value(hadjustment.get_lower())

        self.text_view.queue_draw()
        self.text_scroll.queue_draw()
        self.main_pane.queue_draw()
        return False

    @staticmethod
    def _make_string_factory():
        factory = Gtk.SignalListItemFactory()

        def setup(_factory, list_item):
            label = Gtk.Label(xalign=0)
            label.set_margin_top(5)
            label.set_margin_bottom(5)
            label.set_margin_start(6)
            label.set_margin_end(6)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            list_item.set_child(label)

        def bind(_factory, list_item):
            item = list_item.get_item()
            label = list_item.get_child()
            label.set_text(item.get_string() if item else "")

        factory.connect("setup", setup)
        factory.connect("bind", bind)
        return factory

    @staticmethod
    def _add_tape_filters(dialog):
        tape_filter = Gtk.FileFilter()
        tape_filter.set_name("Tape images (*.tap, *.aws)")
        for pattern in (
            "*.tap",
            "*.TAP",
            "*.aws",
            "*.AWS",
            "*.awstape",
            "*.AWSTAPE",
        ):
            tape_filter.add_pattern(pattern)
        dialog.add_filter(tape_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All files")
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)

    def _active_state(self):
        if (
            self.active_image_index is None
            or self.active_image_index >= len(self.open_images)
        ):
            return None
        return self.open_images[self.active_image_index]

    def _image_status_text(self, image):
        eom_text = " • EOM marker" if image.eom_found else ""
        gap_text = f" • {len(image.gaps)} gap marker(s)" if image.gaps else ""
        return (
            f"{image.path}  •  {image.format_name}  •  "
            f"{len(image.files):,} logical files  •  "
            f"{image.tape_mark_count:,} tape marks  •  "
            f"{image.total_records:,} records  •  "
            f"{image.total_errors:,} error records"
            f"{eom_text}{gap_text}  •  {len(self.open_images):,} image(s) open"
        )

    def _rebuild_image_rows(self):
        while True:
            child = self.image_list.get_first_child()
            if child is None:
                break
            self.image_list.remove(child)

        for index, state in enumerate(self.open_images):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            box.set_margin_start(4)
            box.set_margin_end(4)

            check = Gtk.CheckButton()
            check.set_active(state.compare_selected)
            check.set_tooltip_text("Include this image in Compare")
            check.connect("toggled", self.on_image_compare_toggled, index)
            box.append(check)

            label = Gtk.Label(
                label=f"{os.path.basename(state.image.path)}  •  {state.image.format_name}",
                xalign=0,
            )
            label.set_hexpand(True)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_tooltip_text(state.image.path)
            box.append(label)

            row.set_child(box)
            row.set_activatable(True)
            row.set_selectable(True)
            self.image_list.append(row)

        self._update_compare_button()

    def _update_compare_button(self):
        count = sum(1 for state in self.open_images if state.compare_selected)
        self.compare_button.set_sensitive(count >= 2)
        if count:
            self.compare_button.set_label(f"Compare ({count})")
        else:
            self.compare_button.set_label("Compare")

    def on_image_compare_toggled(self, check, index):
        if index >= len(self.open_images):
            return
        self.open_images[index].compare_selected = check.get_active()
        self._update_compare_button()

    def on_open_clicked(self, _button):
        dialog = Gtk.FileChooserNative.new(
            "Open Tape Images",
            self,
            Gtk.FileChooserAction.OPEN,
            "Open",
            "Cancel",
        )
        dialog.set_select_multiple(True)
        self._add_tape_filters(dialog)
        dialog.connect("response", self.on_file_dialog_response)
        self._file_dialog = dialog
        dialog.show()

    def on_file_dialog_response(self, dialog, response):
        try:
            if response != Gtk.ResponseType.ACCEPT:
                return

            paths = []
            files = dialog.get_files()
            for index in range(files.get_n_items()):
                gio_file = files.get_item(index)
                if gio_file:
                    path = gio_file.get_path()
                    if path:
                        paths.append(path)

            if paths:
                self.load_tapes(paths)
        finally:
            self._file_dialog = None
            dialog.destroy()

    def load_tapes(self, paths):
        existing = {os.path.realpath(state.image.path) for state in self.open_images}
        pending = []
        for path in paths:
            normalized = os.path.realpath(str(Path(path).expanduser()))
            if normalized not in existing and normalized not in pending:
                pending.append(normalized)

        if not pending:
            return False

        self.open_button.set_sensitive(False)
        self.close_button.set_sensitive(False)
        self.convert_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text(
            f"Scanning {len(pending):,} tape image(s)…"
            if len(pending) > 1
            else f"Scanning {pending[0]} …"
        )

        def worker():
            images = []
            errors = []
            for path in pending:
                try:
                    images.append(open_tape_image(path))
                except Exception as exc:
                    errors.append((path, str(exc)))
            GLib.idle_add(self._load_finished, images, errors)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _load_finished(self, images, errors):
        first_new_index = len(self.open_images)
        self.open_images.extend(OpenImageState(image=image) for image in images)

        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self._rebuild_image_rows()

        if images:
            row = self.image_list.get_row_at_index(first_new_index)
            if row:
                self.image_list.select_row(row)

        if errors:
            message = "\n\n".join(f"{path}\n{error}" for path, error in errors)
            self._show_error(
                "Some tape images could not be opened"
                if images
                else "Could not open tape image",
                message,
            )

        if not self.open_images:
            self.status.set_text("No tape images loaded")
            self._set_view_text("No tape images loaded.", "Record view")
        return False

    def on_close_clicked(self, _button):
        if self.active_image_index is None or not self.open_images:
            return

        closing_index = self.active_image_index
        del self.open_images[closing_index]
        self.active_image_index = None
        self.tap = None

        self._rebuild_image_rows()
        self._clear_navigation_models()

        if self.open_images:
            next_index = min(closing_index, len(self.open_images) - 1)
            row = self.image_list.get_row_at_index(next_index)
            if row:
                self.image_list.select_row(row)
        else:
            self.close_button.set_sensitive(False)
            self.convert_button.set_sensitive(False)
            self.set_title("Tape File Browser")
            self.status.set_text("No tape images loaded")
            self._set_view_text(
                "No tape images are open. Click Open… to select one or more images.",
                "Record view",
            )

    def on_image_selected(self, _listbox, row):
        self._clear_navigation_models()

        if row is None:
            self.active_image_index = None
            self.tap = None
            self.close_button.set_sensitive(False)
            self.convert_button.set_sensitive(False)
            return

        index = row.get_index()
        if index < 0 or index >= len(self.open_images):
            return

        self.active_image_index = index
        state = self.open_images[index]
        self.tap = state.image
        image = state.image

        self.close_button.set_sensitive(True)
        self.convert_button.set_sensitive(True)
        self.set_title(f"Tape File Browser — {os.path.basename(image.path)}")
        self.status.set_text(self._image_status_text(image))

        summaries = []
        for tape_file in image.files:
            error_text = f"  •  {tape_file.errors} error" if tape_file.errors else ""
            if tape_file.errors != 1 and tape_file.errors:
                error_text += "s"
            summaries.append(
                f"File {tape_file.number}  •  {len(tape_file.records):,} records"
                f"  •  {tape_file.total_bytes:,} bytes{error_text}"
            )
        self.file_strings.splice(0, self.file_strings.get_n_items(), summaries)

        if image.files:
            state.file_index = min(state.file_index, len(image.files) - 1)
            self._restoring_selection = True
            self.file_selection.set_selected(state.file_index)
            self._restoring_selection = False
        else:
            self._set_view_text(
                f"{image.format_name} tape image contains no logical files.",
                "Record view",
            )

    def on_file_selected(self, selection, _pspec):
        state = self._active_state()
        if not state or not self.tap:
            return

        index = selection.get_selected()
        if index == Gtk.INVALID_LIST_POSITION or index >= len(self.tap.files):
            return

        state.file_index = index
        if not self._restoring_selection:
            state.record_index = 0

        tape_file = self.tap.files[index]
        self.record_heading.set_text(f"Records — File {tape_file.number}")

        summaries = []
        for record in tape_file.records:
            error_text = "  •  ERROR" if record.error else ""
            summaries.append(
                f"Record {record.number:,}  •  {record.length:,} bytes"
                f"  •  0x{record.image_offset:08X}{error_text}"
            )

        self.record_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self.record_strings.splice(0, self.record_strings.get_n_items(), summaries)

        self._set_view_text(
            f"Logical tape file {tape_file.number}\n"
            f"Records: {len(tape_file.records):,}\n"
            f"Data bytes: {tape_file.total_bytes:,}\n"
            f"Error records: {tape_file.errors:,}\n"
            f"Record sizes: {size_summary(tape_file.sizes)}\n\n"
            "Select a record above to display its EBCDIC contents.",
            f"Record view — File {tape_file.number}",
        )

        if tape_file.records:
            state.record_index = min(state.record_index, len(tape_file.records) - 1)
            self.record_selection.set_selected(state.record_index)

    def on_record_selected(self, selection, _pspec):
        state = self._active_state()
        if not state or not self.tap:
            return

        file_index = self.file_selection.get_selected()
        record_index = selection.get_selected()

        if (
            file_index == Gtk.INVALID_LIST_POSITION
            or record_index == Gtk.INVALID_LIST_POSITION
            or file_index >= len(self.tap.files)
        ):
            return

        tape_file = self.tap.files[file_index]
        if record_index >= len(tape_file.records):
            return

        state.record_index = record_index
        record = tape_file.records[record_index]

        try:
            data = self.tap.read_record(record)
        except Exception as exc:
            self._show_error("Could not read record", str(exc))
            return

        status = "ERROR FLAG SET" if record.error else "OK"
        header = (
            f"Format:        {self.tap.format_name}\n"
            f"Tape file:     {tape_file.number}\n"
            f"Record:        {record.number}\n"
            f"Length:        {record.length:,} bytes\n"
            f"Image offset:  {record.image_offset:,} (0x{record.image_offset:X})\n"
            f"Data offset:   {record.data_offset:,} (0x{record.data_offset:X})\n"
            f"Status:        {status}\n"
            f"Encoding:      IBM EBCDIC CP037\n"
            "\n"
        )
        self._set_view_text(
            header + format_ebcdic(data),
            (
                f"Record view — {os.path.basename(self.tap.path)} — "
                f"File {tape_file.number}, Record {record.number}"
            ),
        )

    def _clear_navigation_models(self):
        self.file_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self.record_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self.file_strings.splice(0, self.file_strings.get_n_items(), [])
        self.record_strings.splice(0, self.record_strings.get_n_items(), [])
        self.record_heading.set_text("Records")

    def on_compare_clicked(self, _button):
        selected = [
            state.image for state in self.open_images if state.compare_selected
        ]
        if len(selected) < 2:
            return

        self.open_button.set_sensitive(False)
        self.compare_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text(f"Comparing {len(selected):,} tape images…")

        def worker():
            reference = selected[0]
            reference_hash = logical_sha256(reference)
            lines = [
                f"Reference: {reference.path} ({reference.format_name})",
                f"Logical SHA-256: {reference_hash}",
                "",
            ]
            all_match = True

            for candidate in selected[1:]:
                try:
                    verify_logical_tapes(reference, candidate)
                    candidate_hash = logical_sha256(candidate)
                    if candidate_hash == reference_hash:
                        lines.append(
                            f"IDENTICAL  {candidate.path} ({candidate.format_name})"
                        )
                    else:
                        all_match = False
                        lines.append(
                            f"DIFFERENT  {candidate.path} — logical SHA-256 differs"
                        )
                except Exception as exc:
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
            GLib.idle_add(self._compare_finished, lines, all_match, len(selected))

        threading.Thread(target=worker, daemon=True).start()

    def _compare_finished(self, lines, all_match, count):
        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self._update_compare_button()
        self._set_view_text(
            "\n".join(lines), f"Compare results — {count} images"
        )
        self.status.set_text(
            "All selected tape images are logically identical."
            if all_match
            else "Comparison complete — differences found."
        )
        return False

    def on_convert_clicked(self, _button):
        if not self.tap:
            return

        default_extension = ".aws" if self.tap.format_name == "SIMH" else ".tap"
        default_name = Path(self.tap.path).stem + default_extension

        dialog = Gtk.FileChooserNative.new(
            f"Convert {self.tap.format_name} Tape Image",
            self,
            Gtk.FileChooserAction.SAVE,
            "Convert",
            "Cancel",
        )
        dialog.set_current_name(default_name)
        self._add_tape_filters(dialog)
        dialog.connect("response", self.on_convert_dialog_response)
        self._convert_dialog = dialog
        dialog.show()

    def on_convert_dialog_response(self, dialog, response):
        try:
            if response != Gtk.ResponseType.ACCEPT or not self.tap:
                return

            gio_file = dialog.get_file()
            if not gio_file:
                return
            path = gio_file.get_path()
            if not path:
                return

            suffix = Path(path).suffix.lower()
            if suffix not in {".tap", ".aws", ".awstape"}:
                default_extension = (
                    ".aws" if self.tap.format_name == "SIMH" else ".tap"
                )
                path += default_extension

            self._start_conversion(path)
        finally:
            self._convert_dialog = None
            dialog.destroy()

    def _start_conversion(self, output_path):
        if not self.tap:
            return

        source_path = self.tap.path
        self.open_button.set_sensitive(False)
        self.close_button.set_sensitive(False)
        self.convert_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text(f"Converting to {output_path} …")

        def worker():
            try:
                report = convert_tape(source_path, output_path)
            except Exception as exc:
                GLib.idle_add(self._conversion_failed, str(exc))
                return
            GLib.idle_add(self._conversion_finished, report)

        threading.Thread(target=worker, daemon=True).start()

    def _conversion_finished(self, report: ConversionReport):
        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self.close_button.set_sensitive(self.tap is not None)
        self.convert_button.set_sensitive(self.tap is not None)
        self._update_compare_button()
        self.status.set_text(
            f"Converted and verified {report.records:,} records → {report.output_path}"
        )
        self._show_info(
            "Tape conversion complete",
            report.summary() + f"\n\nOutput: {report.output_path}",
        )
        return False

    def _conversion_failed(self, message):
        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self.close_button.set_sensitive(self.tap is not None)
        self.convert_button.set_sensitive(self.tap is not None)
        self._update_compare_button()
        self.status.set_text("Tape conversion failed")
        self._show_error("Could not convert tape image", message)
        return False

    def _show_error(self, title, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda dlg, _response: dlg.destroy())
        dialog.show()

    def _show_info(self, title, message):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda dlg, _response: dlg.destroy())
        dialog.show()


class TapeBrowserApplication(Gtk.Application):
    def __init__(self, initial_paths=None):
        super().__init__(application_id=APP_ID)
        self.initial_paths = list(initial_paths or [])
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = TapeBrowserWindow(self, self.initial_paths)
        self.window.present()


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Browse SIMH/AWS tape images or convert between the formats."
    )
    parser.add_argument(
        "images",
        nargs="*",
        help="SIMH .tap or AWS .aws image(s) to open",
    )
    parser.add_argument(
        "--convert",
        metavar="OUTPUT",
        help="convert a single input IMAGE to OUTPUT (.tap or .aws), then verify",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

    if args.convert:
        if len(args.images) != 1:
            print(
                "tape-file-browser: --convert requires exactly one input IMAGE",
                file=sys.stderr,
            )
            return 2
        try:
            report = convert_tape(
                str(Path(args.images[0]).expanduser()),
                str(Path(args.convert).expanduser()),
            )
        except Exception as exc:
            print(f"Conversion failed: {exc}", file=sys.stderr)
            return 1
        print(report.summary())
        print(f"Output: {report.output_path}")
        return 0

    initial_paths = [str(Path(path).expanduser()) for path in args.images]
    app = TapeBrowserApplication(initial_paths=initial_paths)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
