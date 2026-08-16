"""DWARF-backed symbol resolver.

Turns a dotted/indexed name like  "s_ekf.x[3]"  or  "mrac_state.roll.What[0]"
into a concrete (address, C type) by walking the firmware ELF's DWARF info.
No hardware needed - this is pure static analysis of OBJ/JX_FLY.axf.

Why DWARF and not the .map: the .map only lists *base* symbols (s_ekf @ 0x...cb4,
572 B). Field offsets and array-element sizes come from the type info, which only
DWARF carries. Resolving from DWARF means the offsets stay correct across rebuilds
automatically - no hand-maintained tables to drift.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Iterator

from elftools.elf.elffile import ELFFile

# PT_LOAD flag constants (from elf.h / pyelftools)
PF_X = 0x1
PF_W = 0x2
PF_R = 0x4

# DWARF constant
DW_TAG_volatile_type = "DW_TAG_volatile_type"

# DWARF DW_ATE_* base-type encodings -> struct format char, keyed by (encoding, size)
_ENCODING = {
    (0x02, 1): "?",  # boolean
    (0x04, 4): "f",  # float
    (0x04, 8): "d",  # double
    (0x05, 1): "b", (0x05, 2): "h", (0x05, 4): "i", (0x05, 8): "q",  # signed
    (0x07, 1): "B", (0x07, 2): "H", (0x07, 4): "I", (0x07, 8): "Q",  # unsigned
    (0x06, 1): "b",  # signed char
    (0x08, 1): "B",  # unsigned char
}


@dataclass(frozen=True)
class Symbol:
    """A fully resolved leaf (scalar) or aggregate the watcher can read."""
    name: str          # canonical name as requested, e.g. "s_ekf.x[3]"
    address: int       # absolute target address
    size: int          # bytes
    fmt: str | None    # struct format char for a scalar leaf, else None (aggregate/opaque)

    @property
    def is_scalar(self) -> bool:
        return self.fmt is not None

    def decode(self, raw: bytes) -> float | int | bool:
        if self.fmt is None:
            raise ValueError(f"{self.name} is an aggregate ({self.size} B); read its fields")
        return struct.unpack("<" + self.fmt, raw[: struct.calcsize(self.fmt)])[0]


@dataclass(frozen=True)
class WritableField:
    """A RAM-resident member that can be written (subject to caller policy)."""
    name: str          # dotted path, e.g. "mrac_state.pitch.What[0]"
    address: int       # absolute RAM address
    c_type: str        # C type as string, e.g. "float"
    size_bytes: int    # sizeof, e.g. 4
    parent: str        # enclosing struct, e.g. "mrac_state.pitch"


class _Type:
    """Minimal resolved-type view: total size, and how to interpret it."""
    __slots__ = ("die", "size", "fmt", "kind")

    def __init__(self, die, size, fmt, kind):
        self.die = die      # underlying (typedef/qualifier-stripped) DIE, or None
        self.size = size    # total bytes
        self.fmt = fmt      # scalar format char, else None
        self.kind = kind    # 'scalar' | 'struct' | 'array' | 'pointer' | 'opaque'


class SymbolResolver:
    """Resolves dotted/indexed variable paths against a firmware ELF's DWARF."""

    def __init__(self, elf_path: str | Path | BytesIO):
        self._from_stream = False
        if isinstance(elf_path, BytesIO):
            self._f = elf_path
            self.elf_path = Path("<BytesIO>")
            self._from_stream = True
        else:
            self.elf_path = Path(elf_path)
            self._f = open(self.elf_path, "rb")
        self._elf = ELFFile(self._f)
        if not self._elf.has_dwarf_info():
            raise ValueError(f"{elf_path} has no DWARF debug info")
        self._dwarf = self._elf.get_dwarf_info()
        self._var_index: dict[str, object] = {}   # name -> variable DIE
        self._build_var_index()

        # Compute writable RAM bounds from PT_LOAD segments (p_flags & PF_W).
        # Use p_vaddr (runtime address) not p_paddr (load address); for ARM
        # bare-metal the two differ when the .data section is loaded from
        # flash and copied into RAM at startup.
        self._ram_lo = None
        self._ram_hi = None
        for seg in self._elf.iter_segments():
            if seg.header.p_type == "PT_LOAD" and (seg.header.p_flags & PF_W):
                lo = seg.header.p_vaddr
                hi = lo + seg.header.p_memsz
                if self._ram_lo is None or lo < self._ram_lo:
                    self._ram_lo = lo
                if self._ram_hi is None or hi > self._ram_hi:
                    self._ram_hi = hi

        # Cache: base_name -> list[WritableField]
        self._writable_cache: dict[str | None, list[WritableField]] = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False

    # ---- public API -----------------------------------------------------

    def resolve(self, path: str) -> Symbol:
        """Resolve 's_ekf.x[3]' -> Symbol(address, size, fmt)."""
        base, steps = _parse_path(path)
        die = self._var_index.get(base)
        if die is None:
            raise KeyError(f"unknown symbol {base!r} "
                           f"(not a global/static variable in {self.elf_path.name})")
        addr = _var_address(die)
        typ = self._resolve_type(die.get_DIE_from_attribute("DW_AT_type"))
        for step in steps:
            addr, typ = self._apply_step(addr, typ, step, base)
        return Symbol(path, addr, typ.size, typ.fmt)

    def names(self) -> list[str]:
        """All resolvable base variable names (for GUI dropdowns / registry building)."""
        return sorted(self._var_index)

    def fields_of(self, path: str) -> list[str]:
        """Immediate member/element names under a struct or array path (for name pickers)."""
        base, steps = _parse_path(path)
        die = self._var_index.get(base)
        if die is None:
            raise KeyError(base)
        typ = self._resolve_type(die.get_DIE_from_attribute("DW_AT_type"))
        addr = _var_address(die)
        for step in steps:
            addr, typ = self._apply_step(addr, typ, step, base)
        if typ.kind == "struct":
            out = []
            for m in typ.die.iter_children():
                if m.tag == "DW_TAG_member" and "DW_AT_name" in m.attributes:
                    out.append(m.attributes["DW_AT_name"].value.decode())
            return out
        if typ.kind == "array":
            n = _array_count(typ.die)
            return [f"[{i}]" for i in range(n)] if n is not None else []
        return []

    def writable_members(self, base_name: str) -> list[WritableField]:
        """Returns every scalar or array-element member of `base_name` whose
        DWARF location describes a RAM address (DW_AT_location is DW_OP_addr).

        - Members with ``const`` qualifier → EXCLUDED.
        - Members in .text or with DW_OP_reg location → EXCLUDED.
        - Members with ``volatile`` → EXPLICITLY INCLUDED (caller decides policy).
        - If ``base_name`` is "" (empty string), walks ALL top-level globals.

        Results are cached per instance.
        """
        cache_key: str | None = base_name if base_name else None
        if cache_key in self._writable_cache:
            return self._writable_cache[cache_key]

        results: list[WritableField] = []
        if base_name:
            base, _ = _parse_path(base_name)
            die = self._var_index.get(base)
            if die is None:
                self._writable_cache[cache_key] = []
                return []
            var_typ = self._resolve_type(die.get_DIE_from_attribute("DW_AT_type"))
            var_addr = _var_address(die)
            results = self._collect_writable(var_addr, var_typ, base_name, base)
        else:
            for name, die in self._var_index.items():
                if self._is_const(die):
                    continue
                if not _is_addr_location(die.attributes["DW_AT_location"].value):
                    continue
                addr = _var_address(die)
                if not self._in_ram(addr):
                    continue
                var_typ = self._resolve_type(die.get_DIE_from_attribute("DW_AT_type"))
                if var_typ.kind == "scalar":
                    results.append(WritableField(
                        name=name,
                        address=addr,
                        c_type=_c_type_name(die),
                        size_bytes=var_typ.size,
                        parent="",
                    ))
                elif var_typ.kind in ("struct", "array"):
                    results.extend(
                        self._collect_writable(addr, var_typ, name, name)
                    )

        results.sort(key=lambda w: w.address)
        self._writable_cache[cache_key] = results
        return results

    def _collect_writable(self, addr: int, typ: _Type, path: str, parent: str
                          ) -> list[WritableField]:
        """Recursively collect writable fields under addr/typ, building dotted paths."""
        out: list[WritableField] = []
        if typ.kind == "scalar":
            out.append(WritableField(
                name=path,
                address=addr,
                c_type=typ.die.attributes["DW_AT_name"].value.decode()
                       if typ.die and "DW_AT_name" in typ.die.attributes
                       else _c_type_fallback(typ),
                size_bytes=typ.size,
                parent=parent,
            ))
        elif typ.kind == "struct":
            for m in typ.die.iter_children():
                if m.tag != "DW_TAG_member":
                    continue
                mname = m.attributes.get("DW_AT_name")
                if not mname:
                    continue
                mname_str = mname.value.decode()
                moff = m.attributes.get("DW_AT_data_member_location")
                off = _member_offset(moff.value) if moff else 0
                mtyp = self._resolve_type(m.get_DIE_from_attribute("DW_AT_type"))
                if mtyp.kind == "scalar":
                    if not self._in_ram(addr + off):
                        continue
                    out.append(WritableField(
                        name=f"{path}.{mname_str}",
                        address=addr + off,
                        c_type=mtyp.die.attributes["DW_AT_name"].value.decode()
                               if mtyp.die and "DW_AT_name" in mtyp.die.attributes
                               else _c_type_fallback(mtyp),
                        size_bytes=mtyp.size,
                        parent=path,
                    ))
                else:
                    out.extend(
                        self._collect_writable(addr + off, mtyp, f"{path}.{mname_str}", path)
                    )
        elif typ.kind == "array":
            elem = self._resolve_type(typ.die.get_DIE_from_attribute("DW_AT_type"))
            n = _array_count(typ.die)
            if n is not None:
                for i in range(n):
                    out.extend(
                        self._collect_writable(addr + i * elem.size, elem,
                                              f"{path}[{i}]", path)
                    )
        return out

    def _in_ram(self, addr: int) -> bool:
        """True when addr falls within any writable PT_LOAD segment."""
        return (self._ram_lo is not None
                and self._ram_hi is not None
                and self._ram_lo <= addr < self._ram_hi)

    def _is_const(self, die) -> bool:
        """True when the variable or its type chain has a const qualifier."""
        # Check the variable's type chain. get_DIE_from_attribute raises KeyError
        # when the DIE has no DW_AT_type (e.g. implicit-sized typedefs or
        # void-typed parameters); fall back to a chain walk that tolerates
        # missing attributes.
        t_attr = die.attributes.get("DW_AT_type")
        if t_attr is None:
            return False
        t = die.get_DIE_from_attribute("DW_AT_type")
        while t is not None:
            if t.tag == "DW_TAG_const_type":
                return True
            t_attr = t.attributes.get("DW_AT_type")
            if t_attr is None:
                return False
            t = t.get_DIE_from_attribute("DW_AT_type")
        return False

    def close(self):
        self._f.close()

    # ---- internals ------------------------------------------------------

    def _build_var_index(self):
        # File-scope variables (globals + file statics) are direct CU children and
        # carry a DW_OP_addr location. Locals on a stack have no static address and
        # are intentionally skipped.
        for cu in self._dwarf.iter_CUs():
            top = cu.get_top_DIE()
            for die in top.iter_children():
                if die.tag != "DW_TAG_variable":
                    continue
                name_at = die.attributes.get("DW_AT_name")
                loc = die.attributes.get("DW_AT_location")
                if not name_at or not loc:
                    continue
                if not _is_addr_location(loc.value):
                    continue
                name = name_at.value.decode()
                # First definition wins; skip duplicate extern declarations.
                self._var_index.setdefault(name, die)

    def _resolve_type(self, die) -> _Type:
        # Strip typedef / const / volatile to the underlying type.
        while die is not None and die.tag in (
            "DW_TAG_typedef", "DW_TAG_const_type",
            "DW_TAG_volatile_type", "DW_TAG_restrict_type",
        ):
            nxt = die.attributes.get("DW_AT_type")
            if nxt is None:  # e.g. 'const void'
                return _Type(die, 0, None, "opaque")
            die = die.get_DIE_from_attribute("DW_AT_type")

        if die is None:
            return _Type(None, 0, None, "opaque")

        tag = die.tag
        if tag == "DW_TAG_base_type":
            enc = die.attributes["DW_AT_encoding"].value
            size = die.attributes["DW_AT_byte_size"].value
            return _Type(die, size, _ENCODING.get((enc, size)), "scalar")
        if tag == "DW_TAG_pointer_type":
            size = die.attributes.get("DW_AT_byte_size")
            size = size.value if size else 4
            return _Type(die, size, "I", "pointer")
        if tag == "DW_TAG_enumeration_type":
            size = die.attributes.get("DW_AT_byte_size")
            size = size.value if size else 4
            return _Type(die, size, {1: "b", 2: "h", 4: "i"}.get(size, "i"), "scalar")
        if tag == "DW_TAG_structure_type" or tag == "DW_TAG_union_type":
            size = die.attributes.get("DW_AT_byte_size")
            return _Type(die, size.value if size else 0, None, "struct")
        if tag == "DW_TAG_array_type":
            return _Type(die, _array_size(die, self), None, "array")
        return _Type(die, 0, None, "opaque")

    def _apply_step(self, addr, typ: _Type, step, base):
        if isinstance(step, str):  # .member
            if typ.kind != "struct":
                raise TypeError(f"{base}: '.{step}' but current type is {typ.kind}")
            member = _find_member(typ.die, step)
            if member is None:
                raise KeyError(f"{base}: no member '{step}'")
            off = member.attributes.get("DW_AT_data_member_location")
            off = _member_offset(off.value) if off else 0
            mtyp = self._resolve_type(member.get_DIE_from_attribute("DW_AT_type"))
            return addr + off, mtyp
        else:  # [index]
            if typ.kind != "array":
                raise TypeError(f"{base}: '[{step}]' but current type is {typ.kind}")
            elem = self._resolve_type(typ.die.get_DIE_from_attribute("DW_AT_type"))
            return addr + step * elem.size, elem


# ---- module-level DWARF helpers ----------------------------------------

def _parse_path(path: str):
    """'s_ekf.x[3]' -> ('s_ekf', ['x', 3])."""
    import re
    tokens = path.strip().split(".")
    base_tok = tokens[0]
    steps: list = []

    def emit(tok):
        m = re.match(r"^([A-Za-z_]\w*)((?:\[\d+\])*)$", tok)
        if not m:
            raise ValueError(f"bad path token {tok!r} in {path!r}")
        if m.group(1):
            steps.append(m.group(1))
        for idx in re.findall(r"\[(\d+)\]", m.group(2)):
            steps.append(int(idx))

    # base may itself carry indices, e.g. "buf[2].x"
    bm = re.match(r"^([A-Za-z_]\w*)((?:\[\d+\])*)$", base_tok)
    if not bm:
        raise ValueError(f"bad base symbol {base_tok!r}")
    base = bm.group(1)
    for idx in re.findall(r"\[(\d+)\]", bm.group(2)):
        steps.append(int(idx))
    for tok in tokens[1:]:
        emit(tok)
    return base, steps


def _is_addr_location(loc) -> bool:
    return len(loc) >= 1 and loc[0] == 0x03  # DW_OP_addr


def _var_address(die) -> int:
    loc = bytes(die.attributes["DW_AT_location"].value)
    if not _is_addr_location(loc):
        raise ValueError(f"{die.attributes['DW_AT_name'].value!r} has no static address")
    return struct.unpack_from("<I", loc, 1)[0]


def _member_offset(val) -> int:
    # DW_AT_data_member_location is usually a constant; occasionally a DW_OP_plus_uconst expr.
    if isinstance(val, int):
        return val
    b = bytes(val)
    if b and b[0] == 0x23:  # DW_OP_plus_uconst
        return _uleb(b, 1)
    return b[0] if b else 0


def _uleb(b, i=0) -> int:
    res = shift = 0
    while i < len(b):
        byte = b[i]; i += 1
        res |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
    return res


def _find_member(struct_die, name):
    for m in struct_die.iter_children():
        if m.tag == "DW_TAG_member" and "DW_AT_name" in m.attributes:
            if m.attributes["DW_AT_name"].value.decode() == name:
                return m
    return None


def _array_count(array_die):
    for c in array_die.iter_children():
        if c.tag == "DW_TAG_subrange_type":
            if "DW_AT_count" in c.attributes:
                return c.attributes["DW_AT_count"].value
            if "DW_AT_upper_bound" in c.attributes:
                ub = c.attributes["DW_AT_upper_bound"].value
                if isinstance(ub, int):
                    return ub + 1
    return None


def _array_size(array_die, resolver: SymbolResolver) -> int:
    elem = resolver._resolve_type(array_die.get_DIE_from_attribute("DW_AT_type"))
    total = elem.size
    for c in array_die.iter_children():
        if c.tag == "DW_TAG_subrange_type":
            if "DW_AT_count" in c.attributes:
                total *= c.attributes["DW_AT_count"].value
            elif "DW_AT_upper_bound" in c.attributes:
                ub = c.attributes["DW_AT_upper_bound"].value
                if isinstance(ub, int):
                    total *= ub + 1
    return total


def _c_type_name(die) -> str:
    """Return the C type name for a leaf type DIE.

    Follows typedef chain; returns the name of the underlying base type.
    """
    while die is not None and die.tag in (
        "DW_TAG_typedef", "DW_TAG_volatile_type",
        "DW_TAG_const_type", "DW_TAG_restrict_type",
    ):
        die = die.get_DIE_from_attribute("DW_AT_type")
    if die is None:
        return "?"
    name_at = die.attributes.get("DW_AT_name")
    if name_at:
        return name_at.value.decode()
    # Fallback for anonymous base types.
    tag = die.tag
    if tag == "DW_TAG_base_type":
        enc = die.attributes.get("DW_AT_encoding")
        sz = die.attributes.get("DW_AT_byte_size")
        if enc and sz:
            enc_v, sz_v = enc.value, sz.value
            if _ENCODING.get((enc_v, sz_v)) == "f":
                return "float"
            if _ENCODING.get((enc_v, sz_v)) == "d":
                return "double"
            if enc_v == 0x05:
                return f"int{sz_v*8}_t"
            if enc_v == 0x07:
                return f"uint{sz_v*8}_t"
            if enc_v == 0x06:
                return "signed char"
            if enc_v == 0x08:
                return "unsigned char"
    return "?"


def _c_type_fallback(typ: _Type) -> str:
    """Return a C type name from a resolved _Type, without re-walking typedefs."""
    if typ.fmt == "f":
        return "float"
    if typ.fmt == "d":
        return "double"
    if typ.fmt in ("b", "h", "i", "q"):
        sz = typ.size
        return f"int{sz * 8}_t"
    if typ.fmt in ("B", "H", "I", "Q"):
        sz = typ.size
        return f"uint{sz * 8}_t"
    if typ.fmt == "?":
        return "bool"
    return "?"
