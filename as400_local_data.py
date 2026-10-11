"""CISC 19/CE QLDA: guarded 1,024-byte job-local data-area window.

Two original CISC images independently corroborate +0x100 D3F0055F,
+0x15D 040400, +0x160 1024 contiguous bytes and the +0x560 boundary
marker 01 in the supported variant. Do not infer associated job identity,
currency/active state, CCSID, or numeric type; CP037 is a display lens.
"""
from as400_capabilities import read_prefix, section

LOCAL_DATA_START = 0x160
LOCAL_DATA_LENGTH = 1024
LOCAL_DATA_END = LOCAL_DATA_START + LOCAL_DATA_LENGTH
PAGE_BYTES = 128
READ_LIMIT = LOCAL_DATA_END + 1


def decode_local_data(data, *, type_code):
    """Fail closed on incomplete or unsupported recovered-primary layouts."""
    if type_code != "19/CE":
        raise ValueError("Not a CISC QLDA primary")
    if len(data) < READ_LIMIT:
        raise ValueError("QLDA value or end marker is not fully recovered; virtual gap/truncation")
    if data[0x100:0x104] != bytes.fromhex("D3F0055F"):
        raise ValueError("Unrecognized QLDA control prefix +0x100")
    if data[0x15D:0x160] != bytes.fromhex("040400"):
        raise ValueError("Unrecognized QLDA value-boundary marker +0x15D")
    if data[LOCAL_DATA_END] != 1:
        raise ValueError("QLDA post-value boundary +0x560 is not the corroborated 01 variant")
    return bytes(data[LOCAL_DATA_START:LOCAL_DATA_END])


def lda_action(name, obj, *, start):
    return dict(kind="lda_action", name=name, type="Local data area",
                note="", request=dict(obj=obj, start=start))


class LocalDataExplorer:
    def __init__(self, image):
        self.image = image
        self._cache = {}

    def data(self, obj):
        if obj.type_code != "19/CE":
            raise ValueError("Not a job-local data area")
        key = (obj.segment.start_lba, obj.segment.virtual_address)
        if key not in self._cache:
            self._cache[key] = decode_local_data(
                read_prefix(self.image, obj.segment, READ_LIMIT),
                type_code=obj.type_code)
        return self._cache[key]

    def rows(self, obj, start=0):
        if not isinstance(start, int) or start < 0 or start >= LOCAL_DATA_LENGTH or start % PAGE_BYTES:
            raise ValueError("LDA START must be a multiple of 128 between 0 and 896")
        value = self.data(obj)
        blank = value.count(0x40)
        end = min(start+PAGE_BYTES, LOCAL_DATA_LENGTH)
        rows = [section("Local data-area bytes", [
            f"Recovered QLDA {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Empirically bounded candidate value: +0x{LOCAL_DATA_START:X}..+0x{LOCAL_DATA_END:X} (end exclusive), {len(value)} bytes",
            f"Exact EBCDIC blank bytes (40): {blank}; other bytes: {len(value)-blank}",
            f"Value positions {start+1}..{end}, one-based; use Next/Previous for all 1024 positions.",
            "This is saved archival LDA content, not a current or proven job-associated LDA.",
            "Hex is exact; CP037 is a display lens, not a verified original CCSID.",
            "No modifications or execution are possible."])]
        if start:
            rows.append(lda_action("Previous 128", obj, start=start-PAGE_BYTES))
        if end < LOCAL_DATA_LENGTH:
            rows.append(lda_action("Next 128", obj, start=end))
        for offset in range(start, end, 32):
            chunk = value[offset:min(offset+32, end)]
            rows.append(section(f"{offset+1}-{offset+len(chunk)}", [
                f"Primary offset +0x{LOCAL_DATA_START+offset:X}; {len(chunk)} bytes",
                f"Hex: {chunk.hex(' ').upper()}",
                f"CP037: {chunk.decode('cp037')!r}",
                "Candidate value positions, not a declared application record."]))
        return rows
