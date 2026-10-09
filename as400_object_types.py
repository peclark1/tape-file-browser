"""Versioned, source-attributed IBM i MI object-type name catalog.

The data files are transcriptions of IBM's published external/internal object
type tables. They label *types*, NOT proof of an object's on-disk structure,
completeness, contents, or availability in OS/400 V2R3.

Only the types in these files are mapped. Unlisted codes stay raw (XX/YY).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re


EXTERNAL_SOURCE = "https://www.ibm.com/docs/en/i/7.5.0?topic=objects-external-object-types"
INTERNAL_SOURCE = "https://www.ibm.com/docs/en/i/7.5.0?topic=concepts-internal-object-types"

_HEX = re.compile(r"^[0-9A-F]{4}$")
_NAME = re.compile(r"^\*[A-Z0-9]+$")


@dataclass(frozen=True)
class ObjectTypeInfo:
    code: str
    name: str
    description: str
    category: str
    source: str

    @property
    def display_code(self):
        return self.code[:2] + "/" + self.code[2:]

    @property
    def type_pair(self):
        return int(self.code[:2], 16), int(self.code[2:], 16)


def parse_catalog(lines, *, category, source):
    """Strictly parse an IBM catalog; conflicting/malformed entries fail fast.

    A bad source must never silently give a confident type name.
    """
    if category not in {"external", "internal"}:
        raise ValueError("Unknown catalog category")
    result = {}
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split("|")]
        if len(fields) != 3:
            raise ValueError(f"{category} catalog line {lineno}: expected three fields")
        code, name, description = fields
        if not _HEX.fullmatch(code) or not _NAME.fullmatch(name) or not description:
            raise ValueError(f"{category} catalog line {lineno}: invalid record")
        if code in result:
            raise ValueError(f"{category} catalog line {lineno}: duplicate {code}")
        result[code] = ObjectTypeInfo(code, name, description, category, source)
    return result


def merge_catalogs(external, internal):
    """Fail on overlapping MI codes; the two IBM tables must be unambiguous."""
    overlap = set(external) & set(internal)
    if overlap:
        raise ValueError(f"Conflicting external/internal MI code(s): {sorted(overlap)}")
    return {**external, **internal}


@lru_cache(maxsize=1)
def catalog():
    root = Path(__file__).resolve().parent
    pairs = (
        ("as400_external_types.tsv", "external", EXTERNAL_SOURCE),
        ("as400_internal_types.tsv", "internal", INTERNAL_SOURCE),
    )
    all_parts = []
    for filename, category, source in pairs:
        path = root / filename
        with path.open("r", encoding="utf-8") as stream:
            all_parts.append(parse_catalog(stream, category=category, source=source))
    return merge_catalogs(*all_parts)


def lookup(type_code, subtype=None):
    """Look up MI code as (type, subtype), '1905', or '19/05'."""
    if subtype is not None:
        if (not isinstance(type_code, int) or not isinstance(subtype, int)
                or not 0 <= type_code <= 255 or not 0 <= subtype <= 255):
            return None
        key = f"{type_code:02X}{subtype:02X}"
    elif isinstance(type_code, str):
        key = type_code.upper().replace("/", "").strip()
        if not _HEX.fullmatch(key):
            return None
    else:
        return None
    return catalog().get(key)


def type_hint(type_code, subtype):
    item = lookup(type_code, subtype)
    return item.name if item is not None else ""
