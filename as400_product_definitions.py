"""Guarded CISC 19/1B saved program-product definition browser.

Distinct archive-backed variants:
- V2R3: EBCDIC 'PDO 11', +0x100 length = 608 + 95*N, +0x358 N,
  +0x356 16+95*N, 95-byte records starting at +0x362.
- B10: EBCDIC 'PDO ' plus zero-control bytes, +0x100 length 496,
  fixed CP037 vendor, product label and legal-text candidate fields.

These are saved product/documentation data, NOT proof of installed product
entitlements, licensing authority, service pack state or executing code.
"""
from dataclasses import dataclass
import fnmatch
import re

from as400_capabilities import section, object_row
from as400_records import read_range

MAX_BYTES = 2 * 1024 * 1024
ROW_START = 0x362
ROW_BYTES = 95
WINDOW = 50
IDENT = re.compile(r"[A-Z0-9]{5,10}")
MESSAGE = re.compile(r"[A-Z][A-Z0-9]{2}[0-9A-F]{4}")
NAMESPACE = re.compile(r"[A-Z#$@][A-Z0-9_#$@]{0,9}")
FILTER = re.compile(r"[A-Z0-9*?]{1,16}")


def padded(raw, pattern=NAMESPACE):
    text = raw.decode("cp037", errors="replace").rstrip(" ")
    return text if pattern.fullmatch(text) and text.ljust(len(raw)).encode("cp037") == raw else None


@dataclass(frozen=True)
class ProductEntry:
    ordinal: int
    offset: int
    raw: bytes
    product: str | None
    namespace: str | None
    message_id: str | None
    variant_digits: str | None


@dataclass(frozen=True)
class ProductDefinition:
    variant: str
    product: str
    release_code: str
    declared_length: int
    entries: tuple[ProductEntry, ...] = ()
    vendor: str = ""
    label: str = ""
    legal: str = ""
    message_file: str | None = None
    message_library: str | None = None


def decode_product_definition(data, *, type_code):
    if type_code != "19/1B":
        raise ValueError("Not a recovered CISC product-definition primary")
    if len(data) < 0x360:
        raise ValueError("Incomplete product-definition header")
    length = int.from_bytes(data[0x100:0x104], "big")
    if length < 1 or length > MAX_BYTES or 0x104 + length > len(data):
        raise ValueError("Saved program-product definition is truncated or oversized")
    product = padded(data[0x209:0x213], IDENT)
    release = data[0x21C:0x224].decode("cp037", errors="replace")
    if not product or not re.fullmatch("[0-9]{8}", release):
        raise ValueError("Unsupported product identifier or saved release-code layout")
    signature = data[0x200:0x206]
    if signature == "PDO 11".encode("cp037"):
        count = int.from_bytes(data[0x358:0x35C], "big")
        measure = int.from_bytes(data[0x356:0x358], "big")
        if (not 1 <= count <= 8192 or length != 608 + ROW_BYTES * count or
                measure != 16 + ROW_BYTES * count):
            raise ValueError("Unsupported saved PDO product-row count/length pair")
        msgfile = padded(data[0x2E0:0x2EA])
        msglib = padded(data[0x2F4:0x2FE])
        records=[]
        for i in range(count):
            offset = ROW_START + i * ROW_BYTES
            raw = bytes(data[offset:offset+ROW_BYTES])
            if len(raw)!=ROW_BYTES:
                raise ValueError("A declared product-row byte span is incomplete")
            prefix = int.from_bytes(raw[:2], "big")
            prod = raw[21:28].decode("cp037", errors="replace")
            namespace = padded(raw[36:46])
            msgid = raw[48:55].decode("cp037", errors="replace")
            digits = raw[28:36].decode("cp037", errors="replace")
            # Reject uncorroborated row-shaped noise without hiding its
            # ordinal/origin and raw bytes. Never invent an MSGF link.
            if (prefix == ROW_BYTES and prod == product and
                    namespace is not None and MESSAGE.fullmatch(msgid) and
                    re.fullmatch("[0-9]{8}", digits)):
                records.append(ProductEntry(i+1, offset, raw, prod,
                                            namespace, msgid, digits))
            else:
                records.append(ProductEntry(i+1, offset, raw, None,
                                            None, None, None))
        return ProductDefinition("v2r3-records",product,release,length,
                                 tuple(records),message_file=msgfile,
                                 message_library=msglib)
    if (signature == "PDO ".encode("cp037") + b"\x00\x00" and
            length == 496):
        vendor = data[0x104:0x136].decode("cp037",errors="replace").strip()
        label = data[0x136:0x148].decode("cp037",errors="replace").strip()
        legal = data[0x228:0x288].decode("cp037",errors="replace").split("\x00")[0].rstrip(" ")
        if not vendor or not legal or not all(32 <= ord(c) <= 126 for c in vendor+label+legal):
            raise ValueError("Unsupported legacy vendor/legal-text candidate encoding")
        return ProductDefinition("b10-text",product,release,length,
                                 vendor=vendor,label=label,legal=legal)
    raise ValueError("Unknown on-disk PDO variant; no V2R3 fields guessed on older records")


def action(name,obj,**kwargs):
    return dict(kind="product_definition_action",name=name,
                type="Archived product definition",note="",
                request=dict(obj=obj,**kwargs))


class ProductDefinitionExplorer:
    def __init__(self,image,inventory,message_explorer=None):
        self.image=image
        self.message_explorer=message_explorer
        self._cache={}
        self._product_peers=tuple(
            sorted((o for o in inventory.objects if o.type_code=="19/1B"),
                   key=lambda o:(o.name,o.library_name or "",o.segment.start_lba)))
        self._msgf={}
        for obj in inventory.objects:
            if obj.type_code=="0E/03":
                key=((obj.library_name or "").upper(),obj.name.upper())
                self._msgf.setdefault(key,[]).append(obj)
        for values in self._msgf.values():
            values.sort(key=lambda o:o.segment.start_lba)

    def definition(self,obj):
        if obj.type_code!="19/1B":
            raise ValueError("Not a recovered program-product definition")
        origin=(obj.segment.start_lba,obj.segment.virtual_address)
        if origin not in self._cache:
            head=read_range(self.image,obj.segment,0,0x360)
            length=int.from_bytes(head[0x100:0x104],"big")
            if length < 1 or length > MAX_BYTES:
                raise ValueError("Unsupported saved product-definition length")
            data=read_range(self.image,obj.segment,0,0x104+length)
            self._cache[origin]=decode_product_definition(data,type_code=obj.type_code)
        return self._cache[origin]

    def rows(self,obj,start=0,msgid="*",entry=None):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid product-definition row window")
        if not isinstance(msgid,str) or not FILTER.fullmatch(msgid):
            raise ValueError("MSGID must be an uppercase identifier glob")
        info=self.definition(obj)
        if entry is not None:
            if info.variant!="v2r3-records" or entry not in info.entries:
                raise ValueError("Chosen row does not belong to this product definition")
            lines=[
                f"PRDDFN {obj.library_name or '<unassigned>'}/{obj.name}; LBA {obj.segment.start_lba}",
                f"Saved entry {entry.ordinal}; primary +0x{entry.offset:X}; exactly {len(entry.raw)} bytes",
                f"Product identifier candidate: {entry.product or '<unsupported row>'}",
                f"Namespace candidate: {entry.namespace or '<unverified>'}",
                f"Message-ID-shaped text: {entry.message_id or '<unverified>'}",
                f"Uninterpreted eight decimal digits: {entry.variant_digits or '<unverified>'}",
                "The row's role, program license, and message linkage are not proven by text alone."
            ]
            rows=[section("Saved product-definition row",lines)]
            for off in range(0,ROW_BYTES,16):
                part=entry.raw[off:off+16]
                rows.append(section(f"Row +0x{off:X}",[
                    part.hex(" ").upper(),
                    repr(part.decode("cp037",errors="replace"))]))
            if entry.message_id and info.message_file and info.message_library:
                candidates=self._msgf.get((info.message_library,info.message_file),())
                rows.append(section("Related saved message-file candidates",[
                    f"Header has {info.message_library}/{info.message_file}; recovered primaries: {len(candidates)}",
                    "Only an exact separately decoded message index entry permits navigation.",
                    "No product activation, installed software or license enforcement is inferred."]))
                for msgf in candidates:
                    rows.append(object_row(msgf,"Saved product header message-file name equality only"))
                    if not self.message_explorer:continue
                    try:
                        message_rows=self.message_explorer.rows(msgf,pattern=entry.message_id)
                    except (ValueError,OSError):
                        rows.append(section("Message index unavailable",[
                            "The saved candidate MSGF index could not be verified; no target guessed."]))
                        continue
                    for hit in message_rows:
                        if (hit.get("kind")=="message_action" and
                                hit.get("name")==entry.message_id and
                                hit.get("request",{}).get("entry") is not None):
                            link=dict(hit)
                            link["note"]=("Exact independently verified message-file ID; "
                                          "choose for separate message-record validation")
                            rows.append(link)
            return rows

        rows=[section("Saved program-product definition",[
            f"PRDDFN {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Supported variant: {info.variant}; candidate product ID: {info.product}",
            f"Archived release-code digits (uninterpreted): {info.release_code}",
            f"Declared saved data length at +0x100: {info.declared_length} bytes",
            "Product/authorization inventory is archival evidence, not proof of installed or licensed entitlements.",
            "Raw EBCDIC is shown through CP037, not a verified source CCSID."])]
        if info.variant=="b10-text":
            rows.append(section("Legacy vendor and product text",[
                f"Vendor text candidate at +0x104: {info.vendor}",
                f"Product/identifier text candidate at +0x136: {info.label}",
                f"Legal-text candidate at +0x228: {info.legal}",
                "Archived promotional/legal strings are not proof of program license or installation."]))
        else:
            matching=[e for e in info.entries if msgid=="*" or
                      (e.message_id and fnmatch.fnmatchcase(e.message_id,msgid))]
            supported=sum(e.message_id is not None for e in info.entries)
            rows.append(section("V2R3 saved 95-byte records",[
                f"Header count +0x358: {len(info.entries)}; supported candidate rows {supported}",
                f"Filtered MSGID({msgid}): {len(matching)}",
                f"Saved message-file name: {info.message_library or '<unknown>'}/{info.message_file or '<unknown>'}",
                "Only supported row candidates expose message-ID links; no program or message is executed."]))
            if start:
                rows.append(action("Previous",obj,start=max(0,start-WINDOW),msgid=msgid))
            if start+WINDOW < len(matching):
                rows.append(action("Next",obj,start=start+WINDOW,msgid=msgid))
            for e in matching[start:start+WINDOW]:
                link=action(e.message_id or f"Unverified row {e.ordinal}",obj,entry=e)
                link["note"]=f"Entry {e.ordinal}; primary +0x{e.offset:X}; preserved original origin"
                rows.append(link)
        peers=[p for p in self._product_peers if p is not obj]
        if peers:
            rows.append(section("Other saved program-product definitions",[
                f"Other recovered 19/1B primaries: {len(peers)}",
                "Select a saved product by its original identity and LBA, not a guessed installed-package list."]))
            rows.extend(object_row(p,"Another archived program-product definition origin") for p in peers[:25])
        return rows
