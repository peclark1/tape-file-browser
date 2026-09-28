#!/usr/bin/env python3

import argparse
import os
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from tape_formats import ConversionReport, TapeImage, convert_tape, open_tape_image
from tape_text import format_ebcdic, size_summary

APP_ID = "com.peclark.TapeFileBrowser"




class TapeBrowserWindow(Gtk.ApplicationWindow):
    def __init__(self, app, initial_path=None):
        super().__init__(application=app)
        self.set_title("Tape File Browser")
        self.set_default_size(1280, 800)

        self.tap: TapeImage | None = None
        self.initial_path = initial_path
        self._file_dialog = None
        self._convert_dialog = None

        self._build_ui()

        if self.initial_path:
            GLib.idle_add(self.load_tape, self.initial_path)

    def _build_ui(self):
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        self.open_button = Gtk.Button(label="Open…")
        self.open_button.set_icon_name("document-open-symbolic")
        self.open_button.connect("clicked", self.on_open_clicked)
        header.pack_start(self.open_button)

        self.convert_button = Gtk.Button(label="Convert…")
        self.convert_button.set_icon_name("document-save-as-symbolic")
        self.convert_button.set_sensitive(False)
        self.convert_button.connect("clicked", self.on_convert_clicked)
        header.pack_start(self.convert_button)

        self.spinner = Gtk.Spinner()
        header.pack_end(self.spinner)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        first_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        first_pane.set_position(275)
        first_pane.set_wide_handle(True)
        outer.append(first_pane)

        file_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        file_box.set_margin_top(8)
        file_box.set_margin_bottom(8)
        file_box.set_margin_start(8)
        file_box.set_margin_end(4)

        file_heading = Gtk.Label(label="Tape files", xalign=0)
        file_heading.add_css_class("heading")
        file_box.append(file_heading)

        self.file_strings = Gtk.StringList.new([])
        self.file_selection = Gtk.SingleSelection.new(self.file_strings)
        # Do not let GTK select row 0 implicitly while the model is being
        # populated.  We select it explicitly after the dependent views are
        # ready so the selection callback always refreshes the record pane.
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
        first_pane.set_start_child(file_box)
        first_pane.set_resize_start_child(False)
        first_pane.set_shrink_start_child(False)

        second_pane = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        second_pane.set_position(360)
        second_pane.set_wide_handle(True)
        first_pane.set_end_child(second_pane)

        record_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        record_box.set_margin_top(8)
        record_box.set_margin_bottom(8)
        record_box.set_margin_start(4)
        record_box.set_margin_end(4)

        self.record_heading = Gtk.Label(label="Records", xalign=0)
        self.record_heading.add_css_class("heading")
        record_box.append(self.record_heading)

        self.record_strings = Gtk.StringList.new([])
        self.record_selection = Gtk.SingleSelection.new(self.record_strings)
        # See file_selection above.  Explicit selection avoids the first
        # record becoming visually selected before notify::selected can drive
        # the EBCDIC pane.
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
        second_pane.set_start_child(record_box)
        second_pane.set_resize_start_child(False)
        second_pane.set_shrink_start_child(False)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        text_box.set_margin_top(8)
        text_box.set_margin_bottom(8)
        text_box.set_margin_start(4)
        text_box.set_margin_end(8)

        self.record_title = Gtk.Label(label="EBCDIC record view", xalign=0)
        self.record_title.add_css_class("heading")
        text_box.append(self.record_title)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_cursor_visible(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.NONE)
        self.text_buffer = self.text_view.get_buffer()
        self.text_buffer.set_text(
            "Open a SIMH .tap or AWS .aws image, select a tape file, then "
            "select a record.\nText is displayed as IBM EBCDIC CP037."
        )

        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        text_scroll.set_hexpand(True)
        text_scroll.set_vexpand(True)
        text_scroll.set_child(self.text_view)
        text_box.append(text_scroll)
        second_pane.set_end_child(text_box)
        second_pane.set_resize_end_child(True)
        second_pane.set_shrink_end_child(False)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        outer.append(separator)

        self.status = Gtk.Label(label="No tape image loaded", xalign=0)
        self.status.set_margin_top(5)
        self.status.set_margin_bottom(5)
        self.status.set_margin_start(8)
        self.status.set_margin_end(8)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        outer.append(self.status)

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

    def on_open_clicked(self, _button):
        dialog = Gtk.FileChooserNative.new(
            "Open Tape Image",
            self,
            Gtk.FileChooserAction.OPEN,
            "Open",
            "Cancel",
        )
        self._add_tape_filters(dialog)
        dialog.connect("response", self.on_file_dialog_response)
        self._file_dialog = dialog
        dialog.show()

    def on_file_dialog_response(self, dialog, response):
        try:
            if response == Gtk.ResponseType.ACCEPT:
                gio_file = dialog.get_file()
                if gio_file:
                    path = gio_file.get_path()
                    if path:
                        self.load_tape(path)
        finally:
            self._file_dialog = None
            dialog.destroy()

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

    def load_tape(self, path):
        self.open_button.set_sensitive(False)
        self.convert_button.set_sensitive(False)
        self.spinner.start()
        self.status.set_text(f"Scanning {path} …")
        self._clear_models()
        self.text_buffer.set_text("Scanning tape image…")

        def worker():
            try:
                image = open_tape_image(path)
            except Exception as exc:
                GLib.idle_add(self._load_failed, path, str(exc))
                return
            GLib.idle_add(self._load_finished, image)

        threading.Thread(target=worker, daemon=True).start()
        return False

    def _load_finished(self, image):
        self.tap = image
        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self.convert_button.set_sensitive(True)

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

        name = os.path.basename(image.path)
        self.set_title(f"Tape File Browser — {name}")
        eom_text = " • EOM marker" if image.eom_found else ""
        gap_text = f" • {len(image.gaps)} gap marker(s)" if image.gaps else ""
        self.status.set_text(
            f"{image.path}  •  {image.format_name}  •  "
            f"{len(image.files):,} logical files  •  "
            f"{image.tape_mark_count:,} tape marks  •  "
            f"{image.total_records:,} records  •  "
            f"{image.total_errors:,} error records"
            f"{eom_text}{gap_text}"
        )

        self.text_buffer.set_text(
            f"{image.format_name} tape image loaded. "
            "Select a logical tape file on the left."
        )

        if image.files:
            self.file_selection.set_selected(0)
        return False

    def _load_failed(self, path, message):
        self.tap = None
        self.spinner.stop()
        self.open_button.set_sensitive(True)
        self.convert_button.set_sensitive(False)
        self.status.set_text(f"Could not open {path}")
        self.text_buffer.set_text(message)
        self._show_error("Could not open tape image", message)
        return False

    def _start_conversion(self, output_path):
        if not self.tap:
            return

        source_path = self.tap.path
        self.open_button.set_sensitive(False)
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
        self.convert_button.set_sensitive(self.tap is not None)
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
        self.convert_button.set_sensitive(self.tap is not None)
        self.status.set_text("Tape conversion failed")
        self._show_error("Could not convert tape image", message)
        return False

    def _clear_models(self):
        self.file_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self.record_selection.set_selected(Gtk.INVALID_LIST_POSITION)
        self.file_strings.splice(0, self.file_strings.get_n_items(), [])
        self.record_strings.splice(0, self.record_strings.get_n_items(), [])
        self.record_heading.set_text("Records")
        self.record_title.set_text("EBCDIC record view")

    def on_file_selected(self, selection, _pspec):
        if not self.tap:
            return

        index = selection.get_selected()
        if index == Gtk.INVALID_LIST_POSITION or index >= len(self.tap.files):
            return

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

        self.record_title.set_text(f"EBCDIC record view — File {tape_file.number}")
        self.text_buffer.set_text(
            f"Logical tape file {tape_file.number}\n"
            f"Records: {len(tape_file.records):,}\n"
            f"Data bytes: {tape_file.total_bytes:,}\n"
            f"Error records: {tape_file.errors:,}\n"
            f"Record sizes: {size_summary(tape_file.sizes)}\n\n"
            "Select a record in the middle pane to display its EBCDIC contents."
        )

        if tape_file.records:
            self.record_selection.set_selected(0)

    def on_record_selected(self, selection, _pspec):
        if not self.tap:
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
        self.record_title.set_text(
            f"EBCDIC record view — File {tape_file.number}, Record {record.number}"
        )
        self.text_buffer.set_text(header + format_ebcdic(data))

        start = self.text_buffer.get_start_iter()
        self.text_view.scroll_to_iter(start, 0.0, False, 0.0, 0.0)

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
    def __init__(self, initial_path=None):
        super().__init__(application_id=APP_ID)
        self.initial_path = initial_path
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = TapeBrowserWindow(self, self.initial_path)
        self.window.present()


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Browse SIMH/AWS tape images or convert between the formats."
    )
    parser.add_argument("image", nargs="?", help="SIMH .tap or AWS .aws image to open")
    parser.add_argument(
        "--convert",
        metavar="OUTPUT",
        help="convert IMAGE to OUTPUT (.tap or .aws), then verify every record",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args(sys.argv[1:])

    if args.convert:
        if not args.image:
            print(
                "tape-file-browser: --convert requires an input IMAGE",
                file=sys.stderr,
            )
            return 2
        try:
            report = convert_tape(
                str(Path(args.image).expanduser()),
                str(Path(args.convert).expanduser()),
            )
        except Exception as exc:
            print(f"Conversion failed: {exc}", file=sys.stderr)
            return 1
        print(report.summary())
        print(f"Output: {report.output_path}")
        return 0

    initial_path = str(Path(args.image).expanduser()) if args.image else None
    app = TapeBrowserApplication(initial_path=initial_path)
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
