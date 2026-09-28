#!/usr/bin/env python3

from collections import Counter

from tape_formats import TapeFile, TapeImage, TapeRecord


def ebcdic_text(data: bytes) -> str:
    """Decode IBM EBCDIC CP037, replacing controls with dots."""
    text = data.decode("cp037", errors="replace")
    return "".join(
        ch if ch.isprintable() and ch not in "\r\n\t" else "." for ch in text
    )


def format_ebcdic(data: bytes, width: int = 64) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        lines.append(f"{offset:04X}: {ebcdic_text(chunk)}")
    return "\n".join(lines)


def format_hex(data: bytes, width: int = 16) -> str:
    """Classic hex dump with an EBCDIC CP037 text column."""
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hex_bytes = " ".join(f"{byte:02X}" for byte in chunk)
        padded = hex_bytes.ljust(width * 3 - 1)
        lines.append(f"{offset:06X}  {padded}  |{ebcdic_text(chunk)}|")
    return "\n".join(lines)


def size_summary(sizes: Counter) -> str:
    if not sizes:
        return "empty"
    return ", ".join(f"{size} x {count}" for size, count in sorted(sizes.items()))


def tape_summary_lines(image: TapeImage) -> list[str]:
    eom = "yes" if image.eom_found else "no"
    return [
        f"Path:          {image.path}",
        f"Format:        {image.format_name}",
        f"Logical files: {len(image.files):,}",
        f"Tape marks:    {image.tape_mark_count:,}",
        f"Records:       {image.total_records:,}",
        f"Payload bytes: {image.total_bytes:,}",
        f"Error records: {image.total_errors:,}",
        f"Gap markers:   {len(image.gaps):,}",
        f"EOM marker:    {eom}",
    ]


def file_summary_line(tape_file: TapeFile) -> str:
    error_text = f", {tape_file.errors} error"
    if tape_file.errors != 1:
        error_text += "s"
    if not tape_file.errors:
        error_text = ""
    return (
        f"File {tape_file.number}: {len(tape_file.records):,} records, "
        f"{tape_file.total_bytes:,} bytes{error_text}"
    )


def record_summary_line(record: TapeRecord) -> str:
    error_text = " ERROR" if record.error else ""
    return (
        f"Record {record.number}: {record.length:,} bytes, "
        f"image 0x{record.image_offset:X}{error_text}"
    )


def record_header(image: TapeImage, tape_file: TapeFile, record: TapeRecord) -> str:
    status = "ERROR FLAG SET" if record.error else "OK"
    return (
        f"Format:        {image.format_name}\n"
        f"Tape file:     {tape_file.number}\n"
        f"Record:        {record.number}\n"
        f"Length:        {record.length:,} bytes\n"
        f"Image offset:  {record.image_offset:,} (0x{record.image_offset:X})\n"
        f"Data offset:   {record.data_offset:,} (0x{record.data_offset:X})\n"
        f"Status:        {status}\n"
        f"Encoding:      IBM EBCDIC CP037\n"
    )
