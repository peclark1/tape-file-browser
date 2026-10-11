"""CISC 19/1D saved product-load metadata and 19/1B PRDDFN correlations.

Mark V2R3 has 40 supported PLO-prefixed product-load *physical*
primary candidates. A strict seven-character EBCDIC code at +0x111
correlates with *PRDDFN identity Q+code in 15 distinct candidates;
the saved +0x164 loader name independently equals the primary name
in all forty. This is an empirical saved *name/code* link, not a
certified product install record pointer, license, install status,
or live software inventory. Pete B10 has no supported 19/1D
primary candidates in the raw physical survey.
"""
from dataclasses import dataclass
import re

from as400_capabilities import object_row, read_prefix, section

READ_LIMIT = 0x17E
HEADER = bytes.fromhex("0000014A") + "PLO ".encode("cp037")
FORMAT = "CV47".encode("cp037")
PRODUCT_CODE = re.compile(r"[0-9]{4}[A-Z0-9]{3}")
IDENTITY = re.compile(r"[A-Z#$@][A-Z0-9_#$@]{0,9}")
DIGITS = re.compile(r"[0-9]{4}")


def _padded_name(raw):
    if len(raw)!=10: return None
    text=raw.decode("cp037",errors="replace").rstrip(" ")
    if not IDENTITY.fullmatch(text) or text.ljust(10).encode("cp037")!=raw:
        return None
    return text


@dataclass(frozen=True)
class ProductLoadEvidence:
    code: str
    saved_loader_name: str
    release_token: str
    saved_name_candidate: str | None
    format_tag: str


def decode_product_load(data, *, type_code, name):
    if type_code!="19/1D":
        raise ValueError("Not an archived product-load primary")
    if len(data)<READ_LIMIT:
        raise ValueError("Truncated saved product-load header or virtual extent")
    if data[0x100:0x108]!=HEADER or data[0x10C:0x110]!=FORMAT:
        raise ValueError("Unsupported saved PLO format/release variant")
    code=data[0x111:0x118].decode("cp037",errors="replace")
    if not PRODUCT_CODE.fullmatch(code):
        raise ValueError("Saved seven-character product-code field malformed")
    release=data[0x118:0x11C].decode("cp037",errors="replace")
    if not DIGITS.fullmatch(release):
        raise ValueError("Unsupported four-character saved PLO release token")
    loader=_padded_name(data[0x164:0x16E])
    if loader is None or loader!=name:
        raise ValueError("Saved loader identity does not equal recovered PLO primary")
    optional=_padded_name(data[0x174:0x17E])
    return ProductLoadEvidence(code,loader,release,optional,"CV47")


class ProductLoadExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self._loads=tuple(x for x in inventory.objects if x.type_code=="19/1D")
        self._definitions=tuple(x for x in inventory.objects if x.type_code=="19/1B")
        self._defs_by_name={}
        for definition in self._definitions:
            self._defs_by_name.setdefault(definition.name.upper(),[]).append(definition)
        for targets in self._defs_by_name.values():
            targets.sort(key=lambda x:(x.library_name or "",x.segment.start_lba))
        self._cache={}
        self._loads_by_code=None
        self._withheld=0

    def load(self,obj):
        if obj.type_code!="19/1D":
            raise ValueError("Not a saved PRDLOD primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            self._cache[key]=decode_product_load(
                read_prefix(self.image,obj.segment,READ_LIMIT),
                type_code=obj.type_code,name=obj.name)
        return self._cache[key]

    def _load_index(self):
        if self._loads_by_code is None:
            by_code={};withheld=0
            for source in self._loads:
                try:evidence=self.load(source)
                except (OSError,ValueError):
                    withheld+=1
                    continue
                by_code.setdefault(evidence.code,[]).append(source)
            for sources in by_code.values():
                sources.sort(key=lambda x:(x.library_name or "",x.name,x.segment.start_lba))
            self._loads_by_code=by_code
            self._withheld=withheld
        return self._loads_by_code

    def rows(self,obj):
        if obj.type_code=="19/1D":
            saved=self.load(obj)
            name="Q"+saved.code
            candidates=self._defs_by_name.get(name,())
            siblings=tuple(x for x in self._load_index().get(saved.code,()) if x is not obj)
            rows=[section("Saved product-load header",[
                f"PRDLOD {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Strict +0x100 0000014A / EBCDIC PLO; +0x10C CV47.",
                f"Saved product code +0x111 (seven characters): {saved.code}",
                f"Saved four-character release-shaped token +0x118: {saved.release_token}",
                f"Recovered name equals saved ten-byte padded identity +0x164: {saved.saved_loader_name}",
                f"Another saved ten-byte name-shaped field +0x174: {saved.saved_name_candidate or '<not supported>'}",
                "These fields are saved metadata; no product installation, release ordering or execution status is established.",
                "Exact product-code/name correlation below is NOT a binary pointer or certified product ownership."])]
            rows.append(section("Matching product-definition names",[
                f"Saved code {saved.code} -> candidate PRDDFN identity {name}",
                f"Independently recovered *PRDDFN primaries with that exact name: {len(candidates)}",
                "Match by strictly decoded code plus Q prefix only; duplicated definitions remain separate."]))
            rows.extend(object_row(t,"Exact saved product code/name correlation; choose PRDDFN origin")
                        for t in candidates)
            rows.append(section("Other saved product loads with same code",[
                f"Other supported PRDLOD origins storing exactly {saved.code}: {len(siblings)}",
                f"Unsupported PRDLOD primaries withheld: {self._withheld}",
                "Same product token is not proof of active release or installed product state."]))
            rows.extend(object_row(o,"Same saved seven-character code; separate archived PLO origin")
                        for o in siblings[:50])
            if len(siblings)>50:
                rows.append(section("Additional loaders",[
                    f"{len(siblings)-50} additional matching loader identities not expanded."]))
            return rows
        if obj.type_code=="19/1B":
            code=obj.name[1:] if obj.name.startswith("Q") else ""
            matches=self._load_index().get(code,()) if PRODUCT_CODE.fullmatch(code) else ()
            rows=[section("Product-definition identity and saved loader candidates",[
                f"PRDDFN {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Exact identity candidate Q + seven-character product code: {code or '<not applicable>'}",
                f"Recovered PRDLOD primaries independently storing this seven-character code: {len(matches)}",
                f"PRDLOD source primaries with unsupported headers: {self._withheld}",
                "This reverse relationship compares archive name/code fields, not a certified installed product or pointer.",
                "PRDDFN object body/layout is not decoded by this view; no product or license fields inferred."])]
            rows.extend(object_row(o,"Exact saved code equals this definition identity after Q prefix")
                        for o in matches[:50])
            if len(matches)>50:
                rows.append(section("Additional load records",[
                    f"{len(matches)-50} matching PRDLOD origins not expanded in this view."]))
            return rows
        raise ValueError("Not a recovered PRDLOD or PRDDFN primary")
