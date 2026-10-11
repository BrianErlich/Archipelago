# ruff: noqa: T201  (command-line tool: printing is its output)
"""
bj3_probe.py - Phase 0 reverse-engineering helper for Bejeweled 3 (PC). READ-ONLY.

The game process is opened with PROCESS_VM_READ | PROCESS_QUERY_INFORMATION only,
so this script cannot write game memory even by accident.

Not part of the shipped .apworld (tools/ is excluded via .apignore).
Needs: pymem (ships with AP >= 0.6.7) and numpy (dev only: `pip install numpy`).

Run from the Archipelago folder with the venv python, e.g.
    .venv\\Scripts\\python worlds\\bejeweled3\\tools\\bj3_probe.py info

Commands
    info                         process, exe version, module base, PE sections, sanity checks
    watch [--chain N=SPEC ...]   live-read pointer chains every 0.5 s (Ctrl+C to stop)
    walk SPEC [SPEC ...]         show every hop of a chain with the C++ class of each object
    objtree SPEC [--class Board] follow pointers from an object; list reachable objects by C++ class
    fields SPEC [--value V]      list an object's fields (pointers to classes, or fields equal to V)
    findobj CLASS                find every live object whose C++ class name contains CLASS
    rtti ADDR                    print the C++ class name of the object at ADDR (MSVC RTTI)
    scan new --value V           Cheat-Engine style value search over writable memory
    scan next (--value V | --changed | --unchanged | --increased | --decreased)
    scan show                    list current scan candidates
    ptrscan ADDR                 find static pointer chains (module+RVA, offsets...) to ADDR
    ptrcheck --value V           keep only saved chains that still resolve to V (after a restart)
    dump NAME                    snapshot all writable memory to probe_out/NAME.npz
    diff A B [--then C]          addresses whose value changed between dumps A and B
    files                        locate profile/save files on disk

Chain SPEC format:  RVA,OFF1,OFF2,...[:TYPE]   (hex; TYPE = i32 | u32 | u8 | i16 | f32 | f64 | vtable | wstr)
    addr = module_base + RVA; for each OFF: addr = read_u32(addr) + OFF; then read TYPE at addr.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import struct
import sys
import time
from pathlib import Path

try:
    import numpy as np
except ImportError:  # only the scan/dump/diff/ptrscan commands need it
    np = None

import pymem
import pymem.exception
import pymem.process

OUT_DIR = Path(__file__).resolve().parent / "probe_out"

# Candidate process names. NOTE: other PopCap games (e.g. Peggle) also run as popcapgame1.exe,
# so a process is only accepted if its exe's ProductName says "Bejeweled 3".
PROCESS_NAMES = ("Bejeweled3.exe", "popcapgame1.exe")

# Chains from redstone59/Bejeweled3WorldChampionships, which targets popcapgame1.exe.
# UNVERIFIED on the Steam build: on Steam 1.1.12.4196 the RVA 0x487F34 lies in .rdata (read-only),
# so these are expected to be garbage there. Kept only as a comparison.
REDSTONE_CHAINS = {
    "rs_board_vtable": "487F34,BE0,0:vtable",
    "rs_score": "487F34,BE0,D20:i32",
    "rs_level": "487F34,BE0,E04:i32",
    "rs_quest_id": "487F34,BE0,322C:i32",
}

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
ERROR_ACCESS_DENIED = 5
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
WRITABLE = {0x04, 0x08, 0x40, 0x80}  # RW, WRITECOPY, EXEC_RW, EXEC_WRITECOPY
TYPES = {"i32": ("<i4", 4), "u32": ("<u4", 4), "u8": ("<u1", 1), "i16": ("<i2", 2),
         "f32": ("<f4", 4), "f64": ("<f8", 8)}
STRUCT_FMT = {"i32": "<i", "u32": "<I", "u8": "<B", "i16": "<h", "f32": "<f", "f64": "<d"}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
version_dll = ctypes.WinDLL("version")


# --------------------------------------------------------------------------- process discovery

def exe_path_of(pid: int) -> str | None:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(h)


def file_version_info(path: str) -> dict:
    """FileVersion (from VS_FIXEDFILEINFO) and ProductName of an exe."""
    info = {"file_version": None, "product_name": None}
    size = version_dll.GetFileVersionInfoSizeW(path, None)
    if not size:
        return info
    data = ctypes.create_string_buffer(size)
    if not version_dll.GetFileVersionInfoW(path, 0, size, data):
        return info
    ptr, ln = ctypes.c_void_p(), wt.UINT()
    if version_dll.VerQueryValueW(data, "\\", ctypes.byref(ptr), ctypes.byref(ln)) and ln.value >= 52:
        ms, ls = struct.unpack_from("<II", ctypes.string_at(ptr.value, 52), 8)
        info["file_version"] = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    if version_dll.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(ln)) \
            and ln.value >= 4:
        lang, cp = struct.unpack("<HH", ctypes.string_at(ptr.value, 4))
        key = f"\\StringFileInfo\\{lang:04x}{cp:04x}\\ProductName"
        if version_dll.VerQueryValueW(data, key, ctypes.byref(ptr), ctypes.byref(ln)) and ln.value:
            info["product_name"] = ctypes.wstring_at(ptr.value, ln.value).rstrip("\0")
    return info


def find_game(pid: int | None = None, names=PROCESS_NAMES) -> tuple[int, str, str, dict]:
    """Return (pid, process name, exe path, version info) of the running Bejeweled 3."""
    rejected = []
    for proc in pymem.process.list_processes():
        name = proc.szExeFile.decode(errors="replace")
        if pid is not None:
            if proc.th32ProcessID != pid:
                continue
        elif name.lower() not in {n.lower() for n in names}:
            continue
        path = exe_path_of(proc.th32ProcessID)
        ver = file_version_info(path) if path else {}
        if pid is not None or (ver.get("product_name") or "").lower().startswith("bejeweled 3"):
            return proc.th32ProcessID, name, path or "?", ver
        rejected.append(f"  skipped pid {proc.th32ProcessID} {name}: product {ver.get('product_name')!r} ({path})")
    msg = "Bejeweled 3 is not running (looked for: " + ", ".join(names) + ")."
    if rejected:
        msg += "\n" + "\n".join(rejected)
    sys.exit(msg)


class Game:
    """Read-only handle on the game process."""

    def __init__(self, pid: int | None = None):
        self.pid, self.name, self.path, self.version = find_game(pid)
        handle = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, self.pid)
        if not handle:
            err = ctypes.get_last_error()
            if err == ERROR_ACCESS_DENIED:
                sys.exit("Access denied opening the game. The game is probably running elevated "
                         "(as administrator) and this script is not. Run both at the same level - "
                         "normally: don't run the game as administrator.")
            sys.exit(f"OpenProcess failed, Windows error {err}")
        self.pm = pymem.Pymem()
        self.pm.process_id = self.pid
        self.pm.process_handle = handle
        mod = pymem.process.base_module(handle)
        if not mod:
            sys.exit("Could not enumerate the game's modules (is it still starting up?)")
        self.base = mod.lpBaseOfDll
        self.image_size = mod.SizeOfImage
        self.sections = self._sections()

    # ---- primitive reads (raise on failure)
    def read(self, addr: int, n: int) -> bytes:
        return self.pm.read_bytes(addr, n)

    def u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    def typed(self, addr: int, typ: str):
        fmt = STRUCT_FMT[typ]
        return struct.unpack(fmt, self.read(addr, struct.calcsize(fmt)))[0]

    def wstring(self, addr: int) -> str:
        """MSVC x86 std::wstring at addr: 16-byte buffer/pointer union, then u32 size, u32 capacity.
        Inline when capacity < 8 wchars, else the first dword is a heap pointer."""
        buf, size, cap = struct.unpack("<16sII", self.read(addr, 24))
        if size > cap or cap > 0x10000:
            raise ValueError(f"not a wstring (size {size}, capacity {cap})")
        data = buf if cap < 8 else self.read(struct.unpack_from("<I", buf)[0], size * 2)
        return data[: size * 2].decode("utf-16-le")

    def cstr(self, addr: int, n: int = 256) -> str:
        raw = self.read(addr, n)
        return raw.split(b"\0", 1)[0].decode("latin-1")

    # ---- PE / module helpers
    def _sections(self) -> list[tuple[str, int, int, int]]:
        hdr = self.read(self.base, 0x1000)
        pe = struct.unpack_from("<I", hdr, 0x3C)[0]
        count = struct.unpack_from("<H", hdr, pe + 6)[0]
        opt = struct.unpack_from("<H", hdr, pe + 20)[0]
        out = []
        for i in range(count):
            name, vsize, va, _, _, _, _, _, _, chars = struct.unpack_from("<8sIIIIIIHHI", hdr, pe + 24 + opt + 40 * i)
            out.append((name.rstrip(b"\0").decode(), va, va + vsize, chars))
        return out

    def section_of(self, addr: int) -> str | None:
        rva = addr - self.base
        for name, start, end, _ in self.sections:
            if start <= rva < end:
                return name
        return None

    def is_static(self, addr: int) -> bool:
        return self.base <= addr < self.base + self.image_size

    def describe(self, addr: int) -> str:
        if self.is_static(addr):
            return f"{self.name}+{addr - self.base:X} ({self.section_of(addr) or 'header'})"
        return f"{addr:08X}"

    # ---- RTTI (MSVC x86): vtable[-1] -> CompleteObjectLocator; COL+12 -> TypeDescriptor; TD+8 -> name
    def rtti_name(self, obj_addr: int) -> str | None:
        try:
            vtable = self.u32(obj_addr)
            return self.rtti_of_vtable(vtable)
        except Exception:
            return None

    def rtti_of_vtable(self, vtable: int) -> str | None:
        try:
            if not self.is_static(vtable):
                return None
            col = self.u32(vtable - 4)
            if not self.is_static(col):
                return None
            td = self.u32(col + 12)
            if not self.is_static(td):
                return None
            name = self.cstr(td + 8)
            return name if name.startswith(".?A") else None
        except Exception:
            return None

    # ---- chains
    def resolve(self, rva: int, offsets: list[int]) -> int:
        addr = self.base + rva
        for off in offsets:
            addr = self.u32(addr) + off
        return addr

    # ---- memory regions
    def regions(self, writable_only=True):
        mbi = MBI()
        addr = 0
        while addr < 0xFFFF0000:
            if not kernel32.VirtualQueryEx(self.pm.process_handle, ctypes.c_void_p(addr),
                                           ctypes.byref(mbi), ctypes.sizeof(mbi)):
                break
            base, size = mbi.BaseAddress or 0, mbi.RegionSize
            if mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_GUARD) and \
                    (not writable_only or (mbi.Protect & 0xFF) in WRITABLE):
                yield base, size
            addr = base + size

    def snapshot(self) -> Snapshot:
        need_numpy()
        bases, lens, chunks, skipped = [], [], [], 0
        for base, size in self.regions():
            try:
                data = self.read(base, size)
            except Exception:
                skipped += 1
                continue
            bases.append(base)
            lens.append(size)
            chunks.append(data)
        snap = Snapshot(np.array(bases, dtype=np.uint64), np.array(lens, dtype=np.uint64),
                        np.frombuffer(b"".join(chunks), dtype=np.uint8))
        snap.skipped = skipped
        return snap


class MBI(ctypes.Structure):
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t),
                    ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]
    else:
        _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                    ("AllocationProtect", wt.DWORD), ("RegionSize", ctypes.c_size_t),
                    ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]


def need_numpy():
    if np is None:
        sys.exit("This command needs numpy:  .venv\\Scripts\\python -m pip install numpy")


# --------------------------------------------------------------------------- snapshots

class Snapshot:
    """All writable memory at one moment: region bases/lengths + one concatenated byte blob."""

    def __init__(self, bases, lens, blob):
        self.bases, self.lens, self.blob = bases, lens, blob
        self.offs = np.concatenate([[0], np.cumsum(lens)[:-1]]).astype(np.uint64) if len(lens) else lens
        self.skipped = 0

    def save(self, path: Path, **meta):
        np.savez(path, bases=self.bases, lens=self.lens, blob=self.blob, meta=json.dumps(meta))

    @classmethod
    def load(cls, path: Path) -> Snapshot:
        d = np.load(path)
        snap = cls(d["bases"], d["lens"], d["blob"])
        snap.meta = json.loads(str(d["meta"]))
        return snap

    def region_views(self, dtype: str):
        size = np.dtype(dtype).itemsize
        for base, ln, off in zip(self.bases, self.lens, self.offs, strict=False):
            n = int(ln) // size * size
            yield int(base), self.blob[int(off):int(off) + n].view(dtype)

    def values_at(self, addrs, dtype: str):
        """(valid mask, values) for an array of addresses."""
        size = np.dtype(dtype).itemsize
        addrs = addrs.astype(np.uint64)
        ri = np.searchsorted(self.bases, addrs, side="right").astype(np.int64) - 1
        ok = ri >= 0
        ri_c = np.where(ok, ri, 0)
        ok &= addrs + np.uint64(size) <= self.bases[ri_c] + self.lens[ri_c]
        pos = self.offs[ri_c] + (addrs - self.bases[ri_c])
        pos = np.where(ok, pos, 0).astype(np.int64)
        raw = np.stack([self.blob[pos + j] for j in range(size)], axis=1).copy()
        return ok, raw.view(dtype).reshape(-1)


# --------------------------------------------------------------------------- commands

def parse_chain(spec: str) -> tuple[int, list[int], str]:
    body, _, typ = spec.partition(":")
    parts = [int(p, 16) for p in body.split(",") if p.strip()]
    return parts[0], parts[1:], (typ or "i32")


def fmt_chain(rva: int, offs: list[int]) -> str:
    return ",".join(f"{x:X}" for x in [rva, *offs])


def cmd_info(g: Game, args):
    print(f"process      : {g.name}  (pid {g.pid})")
    print(f"exe path     : {g.path}")
    print(f"product      : {g.version.get('product_name')}")
    print(f"file version : {g.version.get('file_version')}")
    print(f"module base  : 0x{g.base:08X}   image size 0x{g.image_size:X}")
    print("sections     :")
    for name, start, end, chars in g.sections:
        w = "W" if chars & 0x80000000 else "-"
        print(f"   {name:8s} RVA {start:08X}-{end:08X}  {'R' if chars & 0x40000000 else '-'}{w}"
              f"{'X' if chars & 0x20000000 else '-'}")
    rva = 0x487F34
    try:
        there = f"0x{g.u32(g.base + rva):08X}"
    except Exception:
        there = "unreadable"
    print(f"redstone RVA 0x{rva:X} lies in: {g.section_of(g.base + rva)}  "
          f"(value there: {there}; UNVERIFIED, see REDSTONE_CHAINS)")
    total = sum(s for _, s in g.regions())
    print(f"writable memory: {total / 2**20:.0f} MiB")


def cmd_watch(g: Game, args):
    chains = dict(REDSTONE_CHAINS) if args.redstone else {}
    saved = OUT_DIR / "chains.json"
    if saved.exists() and not args.no_saved:
        chains.update(json.loads(saved.read_text()))
    for c in args.chain or []:
        name, _, spec = c.partition("=")
        chains[name] = spec
    if not chains:
        sys.exit("No chains to watch. Use --chain NAME=SPEC, --redstone, or add them to probe_out/chains.json")
    print(f"watching {len(chains)} chain(s); Ctrl+C to stop")
    last = None
    try:
        while True:
            parts = []
            for name, spec in chains.items():
                rva, offs, typ = parse_chain(spec)
                try:
                    addr = g.resolve(rva, offs)
                    if typ == "vtable":
                        vt = g.u32(addr)
                        val = f"{g.rtti_of_vtable(vt) or 'no-rtti'}@{vt:08X}"
                    elif typ == "wstr":
                        val = repr(g.wstring(addr))
                    else:
                        val = g.typed(addr, typ)
                except Exception:
                    val = "??"
                parts.append(f"{name}={val}")
            if not args.changes or parts != last:
                print(time.strftime("%H:%M:%S ") + "  ".join(parts), flush=True)
            last = parts
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


def cmd_walk(g: Game, args):
    specs = list(args.spec)
    if args.saved:
        data = json.loads((OUT_DIR / args.saved).read_text())
        specs += [fmt_chain(r["rva"], r["offsets"]) + ":" + data.get("type", "i32") for r in data["chains"]]
    for spec in specs:
        rva, offs, typ = parse_chain(spec)
        print(spec)
        addr = g.base + rva
        try:
            for off in offs:
                obj = g.u32(addr)
                print(f"   [{g.describe(addr)}] -> {obj:08X} {g.rtti_name(obj) or '(no RTTI)'}   +{off:X}")
                addr = obj + off
            if typ == "vtable":
                val = g.rtti_name(addr)
            else:
                val = repr(g.wstring(addr)) if typ == "wstr" else g.typed(addr, typ)
            print(f"   value @ {addr:08X} = {val}")
        except Exception as e:
            print(f"   read failed: {e}")


def _object_fields(g: Game, obj: int, size: int, cache: dict):
    """Yield (offset, value, rtti class or None) for each dword of the object."""
    try:
        raw = g.read(obj, size)
    except Exception:
        try:  # object near the end of a region: read what we can, page by page
            raw = b""
            while len(raw) < size:
                raw += g.read(obj + len(raw), 0x1000 - ((obj + len(raw)) & 0xFFF))
        except Exception:
            pass
    for off in range(0, len(raw) - 3, 4):
        val = struct.unpack_from("<I", raw, off)[0]
        cls = None
        if 0x10000 <= val < 0xFFFF0000 and not val & 3 and not g.is_static(val):
            if val not in cache:
                cache[val] = g.rtti_name(val)
            cls = cache[val]
        yield off, val, cls


def cmd_objtree(g: Game, args):
    rva, offs, _ = parse_chain(args.spec)
    root = g.resolve(rva, offs)
    size = int(args.size, 16)
    cache: dict[int, str | None] = {}
    seen = {root}
    frontier = [(root, [])]
    print(f"root {root:08X} {g.rtti_name(root)}")
    for depth in range(1, args.depth + 1):
        nxt = []
        for obj, path in frontier:
            for off, val, cls in _object_fields(g, obj, size, cache):
                if not cls or val in seen:
                    continue
                seen.add(val)
                p = [*path, off]
                if args.cls.lower() in cls.lower():
                    print(f"  {args.spec.split(':')[0]},{','.join(f'{x:X}' for x in p)}  -> {val:08X} {cls}")
                nxt.append((val, p))
        frontier = nxt
        print(f"depth {depth}: {len(nxt)} object(s) reached")


def cmd_fields(g: Game, args):
    rva, offs, _ = parse_chain(args.spec)
    obj = g.resolve(rva, offs)
    print(f"{obj:08X} {g.rtti_name(obj)}")
    if args.text:
        _find_text(g, obj, int(args.size, 16), args.text)
        return
    for off, val, cls in _object_fields(g, obj, int(args.size, 16), {}):
        signed = val - (1 << 32) if val >= 1 << 31 else val
        if args.value is not None:
            if signed == args.value:
                print(f"  +{off:X} = {signed}")
        elif cls:
            print(f"  +{off:X} -> {val:08X} {cls}")


def _find_text(g: Game, obj: int, size: int, text: str):
    """Find TEXT (ASCII or UTF-16) inline in the object, or behind a pointer field (std::string heap buffer)."""
    needles = {"ascii": text.encode("latin-1"), "utf16": text.encode("utf-16-le")}
    try:
        raw = g.read(obj, size)
    except Exception as e:
        sys.exit(f"read failed: {e}")
    for kind, n in needles.items():
        i = raw.find(n)
        while i >= 0:
            print(f"  inline {kind} at +{i:X}")
            i = raw.find(n, i + 1)
    for off in range(0, len(raw) - 3, 4):
        ptr = struct.unpack_from("<I", raw, off)[0]
        if ptr < 0x10000 or ptr & 1:
            continue
        try:
            target = g.read(ptr, len(needles["utf16"]))
        except Exception:
            continue
        for kind, n in needles.items():
            if target.startswith(n):
                print(f"  pointer at +{off:X} -> {ptr:08X} {kind}")


def vtables_matching(g: Game, text: str) -> dict[int, str]:
    """Scan the module image for vtables whose RTTI class name contains TEXT -> {vtable: name}."""
    img = g.read(g.base, g.image_size)
    words = np.frombuffer(img[: len(img) // 4 * 4], dtype="<u4")
    lo, hi = g.base, g.base + g.image_size
    out = {}
    for _name, start, end, chars in g.sections:
        if chars & 0x80000000:  # vtables live in read-only data
            continue
        for i in range(start // 4 + 1, min(end, len(img)) // 4):
            col = int(words[i - 1])
            if not lo <= col < hi - 16:
                continue
            td = int(words[(col - lo) // 4 + 3]) if (col - lo) % 4 == 0 else 0
            if not lo <= td < hi - 8:
                continue
            raw = img[td - lo + 8: td - lo + 120]
            cls = raw.split(b"\0", 1)[0].decode("latin-1")
            if cls.startswith(".?AV") and text.lower() in cls.lower():
                out[lo + i * 4] = cls
    return out


def cmd_findobj(g: Game, args):
    need_numpy()
    vts = vtables_matching(g, args.cls)
    print(f"{len(vts)} vtable(s): " + ", ".join(f"{n}@{v:08X}" for v, n in sorted(vts.items(), key=lambda x: x[1])))
    if not vts:
        return
    snap = g.snapshot()
    keys = np.array(sorted(vts), dtype=np.uint32)
    hits = []
    for base, vals in snap.region_views("<u4"):
        idx = np.nonzero(np.isin(vals, keys))[0]
        hits += [(base + int(i) * 4, int(vals[i])) for i in idx]
    hits.sort(key=lambda h: (vts[h[1]], h[0]))
    print(f"{len(hits)} object(s)")
    for addr, vt in hits[: args.limit]:
        print(f"  {g.describe(addr):40s} {vts[vt]}")


def cmd_rtti(g: Game, args):
    addr = int(args.addr, 16)
    name = g.rtti_name(addr)
    print(f"{g.describe(addr)}: {name or 'no RTTI class (not an object start, or no vtable)'}")
    if args.deref:
        try:
            p = g.u32(addr)
            print(f"  *{addr:08X} = {p:08X} -> {g.rtti_name(p) or 'no RTTI'}")
        except Exception as e:
            print(f"  deref failed: {e}")


def scan_path() -> Path:
    return OUT_DIR / "scan.npz"


def cmd_scan(g: Game, args):
    need_numpy()
    OUT_DIR.mkdir(exist_ok=True)
    if args.action == "show":
        d = np.load(scan_path())
        _print_candidates(g, d["addrs"], d["vals"], args.limit)
        return
    dtype = TYPES[args.type][0]
    snap = g.snapshot()
    if args.action == "new":
        if args.value is None:
            sys.exit("scan new needs --value")
        step = 1 if args.type == "u8" else np.dtype(dtype).itemsize
        found = []
        for base, view in snap.region_views("<u1"):
            if step == 1:
                vals = view.view(dtype)
                idx = np.nonzero(vals == np.array(args.value).astype(dtype))[0]
            else:
                vals = view[: len(view) // step * step].view(dtype)
                idx = np.nonzero(vals == np.array(args.value).astype(dtype))[0] * step
            found.append(np.uint64(base) + idx.astype(np.uint64))
        addrs = np.concatenate(found) if found else np.zeros(0, np.uint64)
        ok, vals = snap.values_at(addrs, dtype)
        addrs, vals = addrs[ok], vals[ok]
    else:
        d = np.load(scan_path())
        if d["type"].item() != args.type:
            sys.exit(f"previous scan was type {d['type'].item()}; pass --type {d['type'].item()}")
        old_addrs, old_vals = d["addrs"], d["vals"]
        ok, vals = snap.values_at(old_addrs, dtype)
        if args.value is not None:
            keep = ok & (vals == np.array(args.value).astype(dtype))
        elif args.changed:
            keep = ok & (vals != old_vals)
        elif args.unchanged:
            keep = ok & (vals == old_vals)
        elif args.increased:
            keep = ok & (vals > old_vals)
        elif args.decreased:
            keep = ok & (vals < old_vals)
        else:
            sys.exit("scan next needs --value, --changed, --unchanged, --increased or --decreased")
        addrs, vals = old_addrs[keep], vals[keep]
    np.savez(scan_path(), addrs=addrs, vals=vals, type=np.array(args.type))
    print(f"{len(addrs)} candidate(s)")
    _print_candidates(g, addrs, vals, args.limit)


def _print_candidates(g, addrs, vals, limit):
    for a, v in list(zip(addrs, vals, strict=False))[:limit]:
        print(f"  {g.describe(int(a)):40s} = {v}")
    if len(addrs) > limit:
        print(f"  ... {len(addrs) - limit} more")


def cmd_ptrscan(g: Game, args):
    need_numpy()
    OUT_DIR.mkdir(exist_ok=True)
    target = int(args.addr, 16)
    maxoff = int(args.max_offset, 16)
    snap = g.snapshot()
    lo, hi = g.base, g.base + g.image_size
    link: dict[int, tuple[int, int]] = {}  # pointer location -> (what it leads to, offset)
    level = np.array([target], dtype=np.uint64)
    results = []
    for depth in range(1, args.depth + 1):
        level = np.unique(level)
        if not len(level):
            break
        found_p, found_t = [], []
        for base, vals in snap.region_views("<u4"):
            vals64 = vals.astype(np.uint64)
            j = np.searchsorted(level, vals64, side="left")
            inb = j < len(level)
            jj = np.where(inb, j, 0)
            hit = inb & (vals64 != 0) & (level[jj] - vals64 <= np.uint64(maxoff))
            idx = np.nonzero(hit)[0]
            if len(idx):
                found_p.append(np.uint64(base) + idx.astype(np.uint64) * np.uint64(4))
                found_t.append(level[jj[idx]])
        if not found_p:
            break
        ps, ts = np.concatenate(found_p), np.concatenate(found_t)
        _, vals_p = snap.values_at(ps, "<u4")
        nxt = []
        for p, t, v in zip(ps.tolist(), ts.tolist(), vals_p.tolist(), strict=False):
            if p in link or p == target:
                continue
            link[p] = (t, t - v)
            if lo <= p < hi:
                offs, cur = [], p
                while cur != target:
                    cur, off = link[cur]
                    offs.append(off)
                results.append({"rva": p - g.base, "offsets": offs})
            else:
                nxt.append(p)
        print(f"depth {depth}: {len(ps)} pointer(s), {len(results)} static chain(s) so far")
        if len(nxt) > args.max_level:
            print(f"  capping next level at {args.max_level} of {len(nxt)} (use --max-level to raise)")
            nxt = nxt[: args.max_level]
        level = np.array(nxt, dtype=np.uint64)
    results.sort(key=lambda r: (len(r["offsets"]), sum(r["offsets"])))
    out = OUT_DIR / (args.out or "ptrscan.json")
    out.write_text(json.dumps({"target": target, "type": args.type, "chains": results}, indent=1))
    print(f"{len(results)} static chain(s) written to {out}")
    for r in results[: args.limit]:
        print(f"  {fmt_chain(r['rva'], r['offsets'])}:{args.type}   [{g.section_of(g.base + r['rva'])}]")


def cmd_ptrcheck(g: Game, args):
    path = OUT_DIR / (args.file or "ptrscan.json")
    data = json.loads(path.read_text())
    typ = args.type or data.get("type", "i32")
    keep = []
    for r in data["chains"]:
        try:
            want = float(args.value) if typ[0] == "f" else int(args.value)
            if g.typed(g.resolve(r["rva"], r["offsets"]), typ) == want:
                keep.append(r)
        except Exception:
            pass
    print(f"{len(keep)} of {len(data['chains'])} chain(s) still resolve to {args.value}")
    data["chains"] = keep
    path.write_text(json.dumps(data, indent=1))
    for r in keep[: args.limit]:
        print(f"  {fmt_chain(r['rva'], r['offsets'])}:{typ}")


def cmd_dump(g: Game, args):
    need_numpy()
    OUT_DIR.mkdir(exist_ok=True)
    snap = g.snapshot()
    path = OUT_DIR / f"{args.name}.npz"
    snap.save(path, base=g.base, image_size=g.image_size, version=g.version.get("file_version"),
              time=time.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"dumped {len(snap.bases)} regions, {len(snap.blob) / 2**20:.0f} MiB -> {path}"
          + (f" ({snap.skipped} unreadable regions skipped)" if snap.skipped else ""))


def cmd_diff(args):
    need_numpy()
    a, b = (Snapshot.load(OUT_DIR / f"{n}.npz") for n in (args.a, args.b))
    c = Snapshot.load(OUT_DIR / f"{args.then}.npz") if args.then else None
    dtype = TYPES[args.type][0]
    size = np.dtype(dtype).itemsize
    base, image_size = a.meta["base"], a.meta["image_size"]
    b_regions = {int(x): i for i, x in enumerate(b.bases)}
    rows = []
    for k, (ra, va) in enumerate(a.region_views(dtype)):
        i = b_regions.get(ra)
        if i is None or int(b.lens[i]) != int(a.lens[k]):
            continue
        off = int(b.offs[i])
        vb = b.blob[off: off + len(va) * size].view(dtype)
        mask = va != vb
        if args.frm is not None:
            mask &= va == np.array(args.frm).astype(dtype)
        if args.to is not None:
            mask &= vb == np.array(args.to).astype(dtype)
        idx = np.nonzero(mask)[0]
        if not len(idx):
            continue
        addrs = np.uint64(ra) + idx.astype(np.uint64) * np.uint64(size)
        old, new = va[idx], vb[idx]
        if c is not None:
            ok, vc = c.values_at(addrs, dtype)
            keep = ok & (vc == new)
            addrs, old, new = addrs[keep], old[keep], new[keep]
        rows.extend(zip(addrs.tolist(), old.tolist(), new.tolist(), strict=False))
    print(f"{len(rows)} changed value(s) ({args.type})")
    for addr, old, new in rows[: args.limit]:
        loc = f"exe+{addr - base:X}" if base <= addr < base + image_size else f"{addr:08X}"
        print(f"  {loc:24s} {old} -> {new}")
    if len(rows) > args.limit:
        print(f"  ... {len(rows) - args.limit} more (raise --limit, or narrow with --from/--to/--then)")


def cmd_files(args):
    roots = [os.environ.get("PROGRAMDATA"), os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"),
             os.path.expanduser("~/Documents")]
    hits = []
    for root in filter(None, roots):
        for dirpath, dirnames, filenames in os.walk(root):
            depth = Path(dirpath).relative_to(root).parts
            if len(depth) > 5:
                dirnames.clear()
                continue
            for f in filenames:
                if f.lower() in {"users.dat", "profile.dat", "hiscores.dat"}:
                    p = Path(dirpath) / f
                    hits.append(p)
    if not hits:
        print("No users.dat / profile.dat / hiscores.dat found under ProgramData, AppData or Documents.")
    for p in hits:
        st = p.stat()
        print(f"  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}  {st.st_size:8d}  {p}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pid", type=int, help="attach to this pid instead of searching by name")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info")
    p = sub.add_parser("watch")
    p.add_argument("--chain", action="append", help="NAME=RVA,OFF,...[:TYPE] (hex)")
    p.add_argument("--redstone", action="store_true", help="also show redstone59's (unverified) chains")
    p.add_argument("--no-saved", action="store_true", help="ignore probe_out/chains.json")
    p.add_argument("--interval", type=float, default=0.5)
    p.add_argument("--changes", action="store_true", help="only print when a value changes")
    p = sub.add_parser("walk")
    p.add_argument("spec", nargs="*", help="RVA,OFF,...[:TYPE]")
    p.add_argument("--saved", help="also walk every chain in this probe_out/ file, e.g. ptrscan.json")
    p = sub.add_parser("objtree")
    p.add_argument("spec", help="chain to the root object, e.g. 4E170C,0 (= Bej3App)")
    p.add_argument("--class", dest="cls", default="", help="only print classes containing this text")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--size", default="2000", help="hex bytes scanned per object (default 0x2000)")
    p = sub.add_parser("fields")
    p.add_argument("spec", help="chain to the object, e.g. 4E170C,B80,0 (= Profile)")
    p.add_argument("--value", type=int, help="only list fields equal to this int")
    p.add_argument("--text", help="find this string inline or behind a pointer field")
    p.add_argument("--size", default="4000", help="hex bytes to scan (default 0x4000)")
    p = sub.add_parser("findobj")
    p.add_argument("cls", help="text contained in the class name, e.g. Badge")
    p.add_argument("--limit", type=int, default=100)
    p = sub.add_parser("rtti")
    p.add_argument("addr", help="hex address")
    p.add_argument("--deref", action="store_true", help="also treat ADDR as a pointer to an object")
    p = sub.add_parser("scan")
    p.add_argument("action", choices=["new", "next", "show"])
    p.add_argument("--value", type=float)
    p.add_argument("--type", default="i32", choices=list(TYPES))
    for flag in ("changed", "unchanged", "increased", "decreased"):
        p.add_argument(f"--{flag}", action="store_true")
    p.add_argument("--limit", type=int, default=40)
    p = sub.add_parser("ptrscan")
    p.add_argument("addr", help="hex address of the value")
    p.add_argument("--type", default="i32", choices=list(TYPES))
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--max-offset", default="4000", help="hex, max offset per level (default 0x4000)")
    p.add_argument("--max-level", type=int, default=20000, help="max non-static pointers carried per level")
    p.add_argument("--out", help="file name in probe_out/ (default ptrscan.json)")
    p.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("ptrcheck")
    p.add_argument("--value", required=True)
    p.add_argument("--type", choices=list(TYPES))
    p.add_argument("--file", help="file name in probe_out/ (default ptrscan.json)")
    p.add_argument("--limit", type=int, default=30)
    p = sub.add_parser("dump")
    p.add_argument("name")
    p = sub.add_parser("diff")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--then", help="third dump; keep only values that stayed at their B value")
    p.add_argument("--type", default="i32", choices=list(TYPES))
    p.add_argument("--from", dest="frm", type=float)
    p.add_argument("--to", type=float)
    p.add_argument("--limit", type=int, default=200)
    sub.add_parser("files")

    args = ap.parse_args()
    if args.cmd == "diff":
        cmd_diff(args)
        return
    if args.cmd == "files":
        cmd_files(args)
        return
    g = Game(args.pid)
    if g.version.get("file_version") != "1.1.12.4196":
        print(f"WARNING: exe version {g.version.get('file_version')} differs from the build this probe "
              f"was written against (1.1.12.4196, Steam).", file=sys.stderr)
    commands = {
        "info": cmd_info, "watch": cmd_watch, "walk": cmd_walk, "objtree": cmd_objtree, "fields": cmd_fields,
        "findobj": cmd_findobj, "rtti": cmd_rtti, "scan": cmd_scan, "ptrscan": cmd_ptrscan, "ptrcheck": cmd_ptrcheck,
        "dump": cmd_dump,
    }
    commands[args.cmd](g, args)
    return


if __name__ == "__main__":
    main()
