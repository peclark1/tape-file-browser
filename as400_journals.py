"""Read-only CISC 09/01 *JRN -> 07/01 *JRNRCV internal-address navigation.

The original Mark V2R3 and Pete B10 archives independently show an
09/01 journal control prefix 00 06 00 1A at primary +0x100, and
full eight-byte internal addresses at primary +0x110 and +0x240.
Each supported slot is compared with the *entire* receiver primary's
segment owner key (extender + six-byte address), not similarly spelled
names or a scan for short address fragments.

These are empirically corroborated *saved receiver-address candidates*,
not certified journal chain chronology, current receiver, or journal
entry contents.
"""
from dataclasses import dataclass

from as400_capabilities import object_row, read_prefix, section
from as400_dasd import InternalAddress

FIRST_AT = 0x110
SECOND_AT = 0x240
ADDRESS_BYTES = 8
READ_LIMIT = SECOND_AT + ADDRESS_BYTES
HEADER_PREFIX = bytes.fromhex("0006001A")
CONTROL_SUFFIX = bytes.fromhex("000A")


@dataclass(frozen=True)
class JournalReceiverAddress:
    offset: int
    address: InternalAddress


def decode_journal_receiver_addresses(data, *, type_code):
    """Require both saved slots and a corroborated cross-release header."""
    if type_code != "09/01":
        raise ValueError("Not a recovered CISC journal")
    if len(data) < READ_LIMIT:
        raise ValueError("Incomplete recovered journal receiver slots or virtual gap")
    if (data[0x100:0x104] != HEADER_PREFIX or
            data[0x106:0x108] != CONTROL_SUFFIX):
        raise ValueError("Unsupported CISC journal control-prefix variant")
    return tuple(
        JournalReceiverAddress(off, InternalAddress.from_bytes(
            data[off:off+ADDRESS_BYTES]))
        for off in (FIRST_AT, SECOND_AT))


class JournalReceiverExplorer:
    def __init__(self, image, inventory):
        self.image = image
        self._journals = tuple(o for o in inventory.objects
                               if o.type_code == "09/01")
        self._receivers = tuple(o for o in inventory.objects
                                if o.type_code == "07/01")
        self._receivers_by_address = {}
        for receiver in self._receivers:
            self._receivers_by_address.setdefault(
                self._identity(receiver), []).append(receiver)
        for receivers in self._receivers_by_address.values():
            receivers.sort(key=lambda o:(o.library_name or "",
                                         o.name, o.segment.start_lba))
        self._saved = {}
        self._reverse = None
        self._withheld = 0

    @staticmethod
    def _identity(obj):
        # Both fields form the segment-owner internal address. Do not
        # equate its six-byte address alone with a recovered receiver.
        return obj.segment.header.owner.key

    def addresses(self, obj):
        if obj.type_code != "09/01":
            raise ValueError("Not a journal primary")
        origin = (obj.segment.start_lba, obj.segment.virtual_address)
        if origin not in self._saved:
            self._saved[origin] = decode_journal_receiver_addresses(
                read_prefix(self.image, obj.segment, READ_LIMIT),
                type_code=obj.type_code)
        return self._saved[origin]

    def _reverse_index(self):
        if self._reverse is None:
            reverse = {}
            missing = 0
            for journal in self._journals:
                try:
                    pointers = self.addresses(journal)
                except (OSError, ValueError):
                    missing += 1
                    continue
                for pointer in pointers:
                    if not pointer.address.is_null:
                        reverse.setdefault(pointer.address.key, []).append(
                            (journal, pointer.offset))
            for links in reverse.values():
                links.sort(key=lambda p:(p[0].library_name or "",p[0].name,
                                         p[0].segment.start_lba,p[1]))
            self._reverse, self._withheld = reverse, missing
        return self._reverse

    def rows(self, obj):
        if obj.type_code == "09/01":
            slots = self.addresses(obj)
            rows = [section("Saved journal receiver addresses", [
                f"JRN {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                "Supported 09/01 control prefix +0x100 and two eight-byte internal-address slots.",
                "Address equality is exact extender + six-byte address, not a name match.",
                "Saved pointers cannot establish current receiver, attached status, order, journal entries or contents.",
                "Select a corroborated receiver origin to inspect reverse source evidence."])]
            for pointer in slots:
                candidates = () if pointer.address.is_null else (
                    self._receivers_by_address.get(pointer.address.key, ()))
                rows.append(section(f"Saved slot +0x{pointer.offset:X}", [
                    f"Full internal address: {pointer.address}",
                    f"Raw eight bytes: {pointer.address.to_bytes().hex(' ').upper()}",
                    f"Recovered *JRNRCV primaries with that exact owner address: {len(candidates)}",
                    "Zero address is a saved null; a missing receiver is not proof of historical absence.",
                    "Slot role and chronology remain unknown."]))
                rows.extend(object_row(target,
                    f"Full address matches journal primary +0x{pointer.offset:X}; role unverified")
                    for target in candidates)
            return rows
        if obj.type_code == "07/01":
            source_key = self._identity(obj)
            links = self._reverse_index().get(source_key, ())
            rows = [section("Saved journal receiver identity", [
                f"JRNRCV {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Full segment-owner address: {obj.segment.header.owner}",
                f"Journal saved slots matching this exact address: {len(links)}",
                f"Unsupported journal source primaries withheld: {self._withheld}",
                "These are saved internal-address occurrences, not proven current attachment or receiver sequence.",
                "No journal-entry bodies or receiver records are decoded."])]
            for journal, offset in links:
                rows.append(object_row(journal,
                    f"Exact receiver owner address appears at journal +0x{offset:X}; follow source"))
            if not links:
                rows.append(section("No saved journal slot match", [
                    "No supported +0x110/+0x240 journal slot matches this complete receiver owner address.",
                    "Other pointer fields, older journal structures or unrecovered primaries remain possible."]))
            return rows
        raise ValueError("Expected saved *JRN or *JRNRCV primary")
