"""Read-only CISC 19/15 compiled PNLGRP tagged-name browser.

V2R3 and B10 primaries have different +0x100 control words; both
contain independently observed tagged EBCDIC name candidates:
13, single-byte length, that many strict printable name bytes.
These are compiled *symbol candidates*, not decoded UIM menu actions,
panel source, command invocation pointers or display instructions.
"""
from dataclasses import dataclass
import fnmatch
import re

from as400_capabilities import read_prefix, section, object_row
from as400_records import read_range

WINDOW_BYTES = 32 * 1024
MAX_NAME_BYTES = 40
PAGE_ENTRIES = 50
SUPPORTED_HEADERS = (bytes.fromhex("00000100"), bytes.fromhex("00000050"))
SYMBOL_NAME = re.compile(r"[A-Z][A-Z0-9_#$@]{3,39}(?:/[A-Z0-9_#$@]{1,20})?")
PATTERN = re.compile(r"[A-Z0-9_#$@/*?]{1,64}")


@dataclass(frozen=True)
class PanelSymbol:
    offset: int
    text: str
    raw: bytes


def decode_panel_symbols(window, base=0):
    """Return tagged name-shaped literals with exact original offsets."""
    if not isinstance(base,int) or base<0 or base%WINDOW_BYTES:
        raise ValueError("Invalid PNLGRP scan-window origin")
    if not isinstance(window,(bytes,bytearray)):
        raise ValueError("Panel scan window must contain bytes")
    found=[]
    for i in range(max(0,0x200-base),max(0,len(window)-5)):
        if window[i]!=0x13:
            continue
        n=window[i+1]
        if not 4<=n<=MAX_NAME_BYTES or i+2+n>len(window):
            continue
        raw=bytes(window[i+2:i+2+n])
        text=raw.decode("cp037",errors="replace")
        if SYMBOL_NAME.fullmatch(text):
            found.append(PanelSymbol(base+i,text,bytes(window[i:i+2+n])))
    return tuple(found)


def action(label,obj,**kwargs):
    return dict(kind="panel_symbol_action",name=label,type="Tagged symbol",
                note="",request=dict(obj=obj,**kwargs))


class PanelGroupExplorer:
    def __init__(self,image,inventory):
        self.image=image
        self._cache={}
        self._cmd_by_name={}
        for cmd in inventory.objects:
            if cmd.type_code=="19/05":
                self._cmd_by_name.setdefault(cmd.name.upper(),[]).append(cmd)
        for values in self._cmd_by_name.values():
            values.sort(key=lambda obj:(obj.library_name or "",obj.segment.start_lba))

    def symbols(self,obj,at=0):
        if obj.type_code!="19/15":
            raise ValueError("Not a compiled panel group")
        if not isinstance(at,int) or at<0 or at%WINDOW_BYTES:
            raise ValueError("AT must be an aligned nonnegative 32768-byte window")
        capacity=obj.segment.pages*512
        if at>=capacity:
            raise ValueError("Requested PNLGRP scan window lies beyond recovered primary")
        key=(obj.segment.start_lba,obj.segment.virtual_address,at)
        if key not in self._cache:
            header=read_prefix(self.image,obj.segment,0x104)
            if len(header)<0x104 or header[0x100:0x104] not in SUPPORTED_HEADERS:
                raise ValueError("Unknown CISC PNLGRP release/header variant")
            length=min(WINDOW_BYTES,capacity-at)
            body=read_range(self.image,obj.segment,at,length)
            self._cache[key]=(decode_panel_symbols(body,at),
                              header[0x100:0x104].hex().upper(),
                              length,capacity)
        return self._cache[key]

    def rows(self,obj,at=0,start=0,name="*",symbol=None):
        if not isinstance(start,int) or start<0:
            raise ValueError("Invalid symbol-results page")
        if not isinstance(name,str) or not PATTERN.fullmatch(name):
            raise ValueError("NAME must be a simple uppercase symbol glob")
        entries,header,window_length,capacity=self.symbols(obj,at)
        if symbol is not None:
            if symbol not in entries:
                raise ValueError("Symbol does not belong to the selected group/window")
            rows=[section("Tagged compiled name",[
                f"PNLGRP {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
                f"Exact primary offset +0x{symbol.offset:X}; tagged bytes {len(symbol.raw)}",
                f"Observed tag 13 / declared literal length {len(symbol.raw)-2}",
                f"Saved literal (CP037 lens): {symbol.text}",
                "Original tagged bytes: "+symbol.raw.hex(" ").upper(),
                "The compiled literal may name a panel, action, help field or keyword; role unresolved.",
                "No UIM instruction, menu behavior or command invocation has been decoded."])]
            # A qualifier before '/' may be a command name. This remains
            # textual correlation, never proof that the symbol calls a CPP.
            left=symbol.text.split("/")[0]
            matches=self._cmd_by_name.get(left,()) if "/" in symbol.text else ()
            if matches:
                rows.append(section("Command-name candidates",[
                    f"Recovered command primaries named {left}: {len(matches)}",
                    "Only a saved name-prefix match, NOT a panel action or binary pointer."]))
                rows.extend(object_row(cmd,"Panel literal prefix match only; command cannot execute")
                            for cmd in matches)
            return rows

        matching=[x for x in entries if fnmatch.fnmatchcase(x.text,name)]
        end=at+window_length
        rows=[section("Compiled panel-group symbols",[
            f"PNLGRP {obj.library_name or '<unassigned>'}/{obj.name}; primary LBA {obj.segment.start_lba}",
            f"Observed release header +0x100: {header}; scanned +0x{at:X}..+0x{end:X} (end exclusive)",
            f"Tagged name candidates in window: {len(entries)}; matching NAME({name}): {len(matching)}",
            "Candidates are 13/length/EBCDIC literal patterns; roles, option actions and pointers unverified.",
            "32 KiB bounded virtual scan windows; text crossing a window boundary may be omitted.",
            "These literals can be absent in compressed/newer PNLGRP variants; no 'no panels' conclusion."])]
        if at:
            rows.append(action("Previous 32 KiB",obj,at=at-WINDOW_BYTES,name=name))
        if end<capacity:
            rows.append(action("Next 32 KiB",obj,at=end,name=name))
        if start:
            rows.append(action("Previous symbols",obj,at=at,start=max(0,start-PAGE_ENTRIES),name=name))
        if start+PAGE_ENTRIES<len(matching):
            rows.append(action("Next symbols",obj,at=at,start=start+PAGE_ENTRIES,name=name))
        for sym in matching[start:start+PAGE_ENTRIES]:
            row=action(sym.text,obj,at=at,name=name,symbol=sym)
            row["note"]=f"+0x{sym.offset:X}; tagged {len(sym.raw)} bytes"
            rows.append(row)
        if not matching:
            rows.append(section("No matching tagged literals",[
                "No supported tagged EBCDIC identifiers matched in this scan window.",
                "This does not prove a panel group has no compiled screen actions or text."]))
        return rows
