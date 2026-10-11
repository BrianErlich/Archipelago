"""
Reading Bejeweled 3's state.

`GameReader` is the interface the client and tests use. `PymemReader` reads the live game (Windows only);
`FakeReader` replays scripted snapshots for tests. The reader only ever opens the game with
PROCESS_VM_READ | PROCESS_QUERY_INFORMATION: it cannot write game memory (SPEC rule 3).

Every tick re-resolves Bej3App -> Profile / Board and re-checks each object's RTTI class (SPEC §7):
a failed read or an unexpected class means "unknown this tick", never a guess.
"""
from __future__ import annotations

import ctypes
import enum
import struct
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol

from .memory_map import MEMORY_MAPS, PRODUCT_NAME, MemoryMap


@dataclass(frozen=True)
class BoardState:
    address: int
    rtti: str
    mode: str | None  # None when it can't be told (yet)
    score: int
    level: int  # 0-based
    quest_index: int | None = None  # 0-39 when this board is a quest


@dataclass(frozen=True)
class Snapshot:
    profile_name: str
    badges: tuple[int, ...]  # tier per badge id (20)
    quests: tuple[int, ...]  # 1 = completed, per quest index (40)
    board: BoardState | None  # None = no board (menus)


class AttachStatus(enum.Enum):
    ATTACHED = "attached"
    NOT_RUNNING = "not_running"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED_VERSION = "unsupported_version"
    NOT_READY = "not_ready"  # process found, but the game objects aren't there (yet)


@dataclass(frozen=True)
class AttachResult:
    status: AttachStatus
    detail: str = ""


ELEVATION_MESSAGE = ("Windows refused access to Bejeweled 3. The game is probably running as administrator and "
                     "this client is not. Run both at the same level; normally that means not running the game "
                     "as administrator.")


class GameReader(Protocol):
    build: str

    def attach(self) -> AttachResult:
        """Find and open the game. Blocking (hundreds of ms): call it from an executor."""

    def read(self) -> Snapshot | None:
        """One snapshot, or None if anything was unreadable or failed validation this tick. Fast: call inline."""

    def alive(self) -> bool:
        """Whether the attached process is still running."""

    def close(self) -> None:
        """Release the process handle."""


# ---------------------------------------------------------------------------------------------------- fake

class FakeReader:
    """Test double: returns scripted results in order; the last one repeats."""

    def __init__(self, snapshots: Iterable[Snapshot | None] = (), attach_results: Iterable[AttachResult] = (),
                 build: str = "Fake 1.0") -> None:
        self.build = build
        self.snapshots: list[Snapshot | None] = list(snapshots)
        self.attach_results = list(attach_results) or [AttachResult(AttachStatus.ATTACHED)]
        self.is_alive = True
        self.closed = False

    def push(self, *snapshots: Snapshot | None) -> None:
        self.snapshots.extend(snapshots)

    def attach(self) -> AttachResult:
        return self.attach_results.pop(0) if len(self.attach_results) > 1 else self.attach_results[0]

    def read(self) -> Snapshot | None:
        if not self.snapshots:
            return None
        return self.snapshots.pop(0) if len(self.snapshots) > 1 else self.snapshots[0]

    def alive(self) -> bool:
        return self.is_alive

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------------------------------- live (Windows)

PROCESS_NAMES = ("bejeweled3.exe", "popcapgame1.exe")
# Boards that derive straight from Board (one mode each). Every other board class derives from QuestBoard.
OWN_BOARDS = frozenset({".?AVClassicBoard@Sexy@@", ".?AVZenBoard@Sexy@@", ".?AVSpeedBoard@Sexy@@"})
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ACCESS_DENIED = 5
STILL_ACTIVE = 259
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
WRITABLE_PROTECTIONS = {0x04, 0x08, 0x40, 0x80}


class ReadError(Exception):
    pass


class PymemReader:
    """Reads the live game. Only constructed on Windows."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("The Bejeweled 3 client only runs on Windows.")
        import ctypes.wintypes as wt

        import pymem.process
        self._wt = wt
        self._pymem_process = pymem.process
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._version = ctypes.WinDLL("version")
        self.build = "not attached"
        self.handle: int | None = None
        self.pid = 0
        self.base = 0
        self.image_size = 0
        self.map: MemoryMap | None = None
        self._rtti_cache: dict[int, str | None] = {}
        self._app_fallback: int | None = None  # Bej3App address found by vtable scan, if the global didn't work

    # ---- attach

    def attach(self) -> AttachResult:
        self.close()
        found = self._find_process()
        if isinstance(found, AttachResult):
            return found
        pid, version = found
        memory_map = MEMORY_MAPS.get(version)
        if memory_map is None:
            supported = ", ".join(m.build for m in MEMORY_MAPS.values())
            return AttachResult(AttachStatus.UNSUPPORTED_VERSION,
                                f"Bejeweled 3 version {version} isn't supported. Supported: {supported}.")
        handle = self._kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
        if not handle:
            if ctypes.get_last_error() == ERROR_ACCESS_DENIED:
                return AttachResult(AttachStatus.ACCESS_DENIED, ELEVATION_MESSAGE)
            return AttachResult(AttachStatus.NOT_RUNNING, f"Couldn't open the game (Windows error "
                                                          f"{ctypes.get_last_error()}).")
        module = self._pymem_process.base_module(handle)
        if not module:
            self._kernel32.CloseHandle(handle)
            return AttachResult(AttachStatus.NOT_READY, "The game is still starting up.")
        self.handle, self.pid, self.map = handle, pid, memory_map
        self.base, self.image_size = module.lpBaseOfDll, module.SizeOfImage
        self.build = memory_map.build
        self._rtti_cache.clear()
        self._app_fallback = None
        if self._app() is None:
            self._app_fallback = self._scan_for_object(memory_map.app_class)
            if self._app_fallback is None:
                return AttachResult(AttachStatus.NOT_READY, "Attached, but the game isn't ready yet.")
        return AttachResult(AttachStatus.ATTACHED, f"Attached to {memory_map.build} (pid {pid}).")

    def _find_process(self) -> tuple[int, str] | AttachResult:
        denied = False
        for proc in self._pymem_process.list_processes():
            name = proc.szExeFile.decode(errors="replace").lower()
            if name not in PROCESS_NAMES:
                continue
            path = self._exe_path(proc.th32ProcessID)
            if path is None:
                denied = True
                continue
            product, version = self._version_info(path)
            if product and product.lower().startswith(PRODUCT_NAME.lower()):
                return proc.th32ProcessID, version or "unknown"
        if denied:
            return AttachResult(AttachStatus.ACCESS_DENIED, ELEVATION_MESSAGE)
        return AttachResult(AttachStatus.NOT_RUNNING, "Waiting for Bejeweled 3 to start.")

    def _exe_path(self, pid: int) -> str | None:
        handle = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = self._wt.DWORD(len(buffer))
            if self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return None
        finally:
            self._kernel32.CloseHandle(handle)

    def _version_info(self, path: str) -> tuple[str | None, str | None]:
        size = self._version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None, None
        data = ctypes.create_string_buffer(size)
        if not self._version.GetFileVersionInfoW(path, 0, size, data):
            return None, None
        ptr, length = ctypes.c_void_p(), self._wt.UINT()
        version = product = None
        if self._version.VerQueryValueW(data, "\\", ctypes.byref(ptr), ctypes.byref(length)) and length.value >= 52:
            ms, ls = struct.unpack_from("<II", ctypes.string_at(ptr.value, 52), 8)
            version = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
        if self._version.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(ptr),
                                        ctypes.byref(length)) and length.value >= 4:
            lang, codepage = struct.unpack("<HH", ctypes.string_at(ptr.value, 4))
            key = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\ProductName"
            if self._version.VerQueryValueW(data, key, ctypes.byref(ptr), ctypes.byref(length)) and length.value:
                product = ctypes.wstring_at(ptr.value, length.value).rstrip("\0")
        return product, version

    def alive(self) -> bool:
        if self.handle is None:
            return False
        code = self._wt.DWORD()
        if not self._kernel32.GetExitCodeProcess(self.handle, ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
        self.handle = None
        self.build = "not attached"

    # ---- primitive reads

    def _read(self, address: int, size: int) -> bytes:
        if self.handle is None or address <= 0 or address >= 0xFFFFFFFF:
            raise ReadError(hex(address))
        buffer = ctypes.create_string_buffer(size)
        done = ctypes.c_size_t()
        if not self._kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer, size,
                                                ctypes.byref(done)) or done.value != size:
            raise ReadError(hex(address))
        return buffer.raw

    def _u32(self, address: int) -> int:
        return struct.unpack("<I", self._read(address, 4))[0]

    def _i32(self, address: int) -> int:
        return struct.unpack("<i", self._read(address, 4))[0]

    def _in_image(self, address: int) -> bool:
        return self.base <= address < self.base + self.image_size

    def rtti_name(self, obj: int) -> str | None:
        """MSVC x86 RTTI: obj -> vtable; vtable[-1] -> CompleteObjectLocator; COL+12 -> TypeDescriptor; TD+8 -> name."""
        vtable = self._u32(obj)
        if vtable in self._rtti_cache:
            return self._rtti_cache[vtable]
        name = None
        if self._in_image(vtable):
            col = self._u32(vtable - 4)
            if self._in_image(col):
                type_descriptor = self._u32(col + 12)
                if self._in_image(type_descriptor):
                    raw = self._read(type_descriptor + 8, 64).split(b"\0", 1)[0].decode("latin-1")
                    name = raw if raw.startswith(".?A") else None
        self._rtti_cache[vtable] = name
        return name

    def _wstring(self, address: int) -> str:
        """MSVC x86 std::wstring: 16-byte buffer/pointer union, u32 size, u32 capacity (inline if capacity < 8)."""
        buffer, size, capacity = struct.unpack("<16sII", self._read(address, 24))
        if size > capacity or capacity > 0x1000:
            raise ReadError("not a wstring")
        data = buffer if capacity < 8 else self._read(struct.unpack_from("<I", buffer)[0], size * 2)
        return data[: size * 2].decode("utf-16-le")

    # ---- per-tick snapshot

    def _app(self) -> int | None:
        assert self.map is not None
        try:
            app = self._u32(self.base + self.map.app_ptr_rva)
            return app if app and self.rtti_name(app) == self.map.app_class else None
        except ReadError:
            return None

    def read(self) -> Snapshot | None:
        memory_map = self.map
        if memory_map is None:
            return None
        try:
            app = self._app()
            if app is None and self._app_fallback is not None:
                if self.rtti_name(self._app_fallback) == memory_map.app_class:
                    app = self._app_fallback
            if app is None:
                return None
            profile = self._u32(app + memory_map.profile_offset)
            if not profile or self.rtti_name(profile) != memory_map.profile_class:
                return None
            name = self._wstring(profile + memory_map.profile_name)
            badges = struct.unpack(f"<{memory_map.badge_count}I",
                                   self._read(profile + memory_map.badge_tiers, 4 * memory_map.badge_count))
            quests = tuple(self._read(profile + memory_map.quests_done, memory_map.quest_count))
            board = None
            board_address = self._u32(app + memory_map.board_offset)
            if board_address:
                rtti = self.rtti_name(board_address)
                if rtti not in memory_map.board_modes:
                    return None
                mode, quest_index = memory_map.board_modes[rtti], None
                if rtti not in OWN_BOARDS:  # quest engine: Quest mode or a secret mode, told apart by the quest id
                    quest_id = self._i32(board_address + memory_map.board_quest_id)
                    if 0 <= quest_id < memory_map.quest_count:
                        mode, quest_index = "Quest", quest_id
                    else:
                        mode = memory_map.secret_mode_ids.get(quest_id)
                board = BoardState(board_address, rtti, mode, self._i32(board_address + memory_map.board_score),
                                   self._i32(board_address + memory_map.board_level), quest_index)
            return Snapshot(name, badges, quests, board)
        except (ReadError, UnicodeDecodeError, struct.error):
            return None

    # ---- fallback: find a singleton object by its class's vtable (SPEC §7 attach guard)

    def _scan_for_object(self, class_name: str) -> int | None:
        vtable = self._find_vtable(class_name)
        if vtable is None:
            return None
        pattern = struct.pack("<I", vtable)
        for base, size in self._writable_regions():
            try:
                data = self._read(base, size)
            except ReadError:
                continue
            index = data.find(pattern)
            while index >= 0:
                if index % 4 == 0 and self.rtti_name(base + index) == class_name:
                    return base + index
                index = data.find(pattern, index + 1)
        return None

    def _find_vtable(self, class_name: str) -> int | None:
        image = self._read(self.base, self.image_size)
        name_at = image.find(class_name.encode() + b"\0")
        if name_at < 8:
            return None
        type_descriptor = self.base + name_at - 8
        col_pattern = struct.pack("<I", type_descriptor)
        index = image.find(col_pattern)
        while index >= 0:
            col = self.base + index - 12
            if index >= 12 and struct.unpack_from("<I", image, index - 12)[0] == 0:  # COL signature 0 on x86
                vtable_at = image.find(struct.pack("<I", col))
                if vtable_at >= 0:
                    return self.base + vtable_at + 4
            index = image.find(col_pattern, index + 1)
        return None

    def _writable_regions(self) -> Iterator[tuple[int, int]]:
        wt = self._wt

        class MemoryBasicInformation(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", wt.DWORD), ("PartitionId", wt.WORD), ("RegionSize", ctypes.c_size_t),
                        ("State", wt.DWORD), ("Protect", wt.DWORD), ("Type", wt.DWORD)]

        info = MemoryBasicInformation()
        address = 0
        while address < 0xFFFF0000:
            if not self._kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(address), ctypes.byref(info),
                                                 ctypes.sizeof(info)):
                return
            base, size = info.BaseAddress or 0, info.RegionSize
            if info.State == MEM_COMMIT and not info.Protect & PAGE_GUARD \
                    and info.Protect & 0xFF in WRITABLE_PROTECTIONS:
                yield base, size
            address = base + size
