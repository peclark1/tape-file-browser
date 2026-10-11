"""Read-only CISC 19/08 EDTD observed edit-pattern and sign-token explorer.

Mark V2R3 QEDIT5..9 and Pete B10 QEDIT6/8 show:
+0x100 EBCDIC decimal digit, +0x124..0x141 a 30-byte
printable CP037 punctuation-shaped region, +0x188 unsigned sign token
length, +0x189.. token characters, +0x1C9 Y/N-shaped flag.
These are empirical *saved pattern candidate* fields, not a certified
numeric formatting interpreter, CCSID specification, or runtime edit code.
"""
from dataclasses import dataclass
import re
from as400_capabilities import read_prefix, section, object_row

TEMPLATE_AT = 0x124
TEMPLATE_LENGTH = 30
SIGN_LENGTH_AT = 0x188
SIGN_AT = 0x189
FLAG_AT = 0x1C9
READ_LIMIT = FLAG_AT + 1


@dataclass(frozen=True)
class EditMaskEvidence:
    digit: str
    template: bytes
    sign: bytes
    flag: bytes


def decode_edit_mask(data, *, type_code, name=""):
    if type_code!="19/08":
        raise ValueError("Not an EDTD primary")
    if len(data)<READ_LIMIT:
        raise ValueError("Truncated edit-description primary")
    if data[0x100] not in range(0xF0,0xFA):
        raise ValueError("Unrecognized saved EDTD EBCDIC-digit header")
    digit=data[0x100:0x101].decode("cp037")
    if re.fullmatch(r"QEDIT[0-9]",name) and digit!=name[-1]:
        raise ValueError("Saved EDTD digit does not match corroborated QEDIT identity")
    template=bytes(data[TEMPLATE_AT:TEMPLATE_AT+TEMPLATE_LENGTH])
    template_text=template.decode("cp037",errors="replace")
    if not all(32<=ord(c)<=126 for c in template_text):
        raise ValueError("Unrecognized or nonprintable edit-template byte")
    length=data[SIGN_LENGTH_AT]
    if length>8 or SIGN_AT+length>=FLAG_AT:
        raise ValueError("Unsupported edit-description sign token length")
    sign=bytes(data[SIGN_AT:SIGN_AT+length])
    sign_text=sign.decode("cp037",errors="replace")
    if not all(32<=ord(c)<=126 for c in sign_text):
        raise ValueError("Nonprintable sign token candidate")
    flag=bytes(data[FLAG_AT:FLAG_AT+1])
    if flag not in (b"\xE8",b"\xD5"):
        raise ValueError("Unsupported saved EDTD Y/N flag variant")
    return EditMaskEvidence(digit,template,sign,flag)


class EditDescriptionExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self._candidates=sorted((o for o in inventory.objects
                                 if o.type_code=="19/08"),
                                key=lambda o:(o.name,o.library_name or "",
                                              o.segment.start_lba))
        self._cache={}

    def evidence(self,obj):
        if obj.type_code!="19/08":
            raise ValueError("Not an edit-description primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address)
        if key not in self._cache:
            self._cache[key]=decode_edit_mask(
                read_prefix(self.image,obj.segment,READ_LIMIT),
                type_code=obj.type_code,name=obj.name)
        return self._cache[key]

    def rows(self,obj):
        e=self.evidence(obj)
        template=e.template.decode("cp037")
        sign=e.sign.decode("cp037")
        flag=e.flag.decode("cp037")
        rows=[section("Saved edit pattern evidence",[
            f"EDTD {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Observed EBCDIC digit at +0x100: {e.digit}",
            f"Candidate 30-byte pattern +0x{TEMPLATE_AT:X}..+0x{TEMPLATE_AT+TEMPLATE_LENGTH:X} (end exclusive)",
            f"Literal CP037 preview, all spaces preserved: {template!r}",
            f"Literal sign token at +0x{SIGN_AT:X} ({len(e.sign)} bytes): {sign!r}",
            f"Observed Y/N-shaped flag at +0x{FLAG_AT:X}: {flag}; meaning not established",
            "Separator-like commas/dashes, zero digits and signs are saved evidence, NOT a certified EDTCDE numeric output rule.",
            "No field changes, runtime formatting, conversion or command execution occurs."])]
        for offset in range(0,TEMPLATE_LENGTH,10):
            part=e.template[offset:offset+10]
            rows.append(section(f"Pattern {offset+1}-{offset+len(part)}",[
                f"Original primary offset +0x{TEMPLATE_AT+offset:X}",
                f"Hex: {part.hex(' ').upper()}",
                f"CP037: {part.decode('cp037')!r}",
                "Position is within candidate saved pattern, not a certified decimal-edit field."]))
        rows.append(section("Sign and flag bytes",[
            f"Sign-length byte +0x{SIGN_LENGTH_AT:X}: {len(e.sign)}",
            f"Literal sign token bytes: {e.sign.hex(' ').upper()}",
            f"Y/N-shaped flag raw hex: {e.flag.hex().upper()}",
            "Some empty sign tokens and Y/N values may be control variants; functions are unknown."]))
        peers=[other for other in self._candidates
               if other is not obj]
        if peers:
            rows.append(section("Other saved edit descriptions",[
                f"{len(peers)} other recovered 19/08 primaries; select an exact origin to compare pattern candidates.",
                "Comparison is by selected saved bytes, never a live OS/400 formatting simulation."]))
            rows.extend(object_row(other,"Compare another saved edit pattern; independent LBA")
                        for other in peers)
        return rows
