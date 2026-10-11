"""
Bejeweled 3 Client: attaches to the running game (read-only), sends checks and reports received items.

All decisions live in tracker.py; all game access lives in game/reader.py. This module wires them to the
Archipelago server: attach state machine, poll loop, DataStorage binding, commands.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable, Sequence
from typing import Any

import colorama

from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, handle_url_arg, server_loop
from NetUtils import ClientStatus
from Utils import async_start, gui_enabled, init_logging

from .game.reader import AttachResult, AttachStatus, GameReader
from .locations import GAME_NAME
from .tracker import GOAL_SHARD_HUNT, Baseline, Tracker

logger = logging.getLogger("Client")

POLL_INTERVAL = 0.3  # seconds between game reads while attached
ATTACH_INTERVAL = 1.0  # seconds between attach attempts while searching


class Bejeweled3CommandProcessor(ClientCommandProcessor):
    ctx: Bejeweled3Context

    def _cmd_bj3(self, subcommand: str = "status") -> bool:
        """Bejeweled 3: "/bj3 status" shows what the client sees; "/bj3 rescan" re-reads the game from scratch."""
        if subcommand == "rescan":
            if self.ctx.tracker is not None:
                self.ctx.tracker.reset_game_state()
            self.output("Re-reading the game from scratch.")
            return True
        if subcommand != "status":
            self.output("Usage: /bj3 status | /bj3 rescan")
            return False
        for line in self.ctx.status_lines():
            self.output(line)
        return True


class Bejeweled3Context(CommonContext):
    game = GAME_NAME
    items_handling = 0b111  # everything comes from the server, including our own items and starting inventory
    command_processor = Bejeweled3CommandProcessor

    def __init__(self, server_address: str | None = None, password: str | None = None,
                 reader_factory: Callable[[], GameReader] | None = None) -> None:
        super().__init__(server_address, password)
        self.reader_factory = reader_factory or _default_reader
        self.reader: GameReader | None = None
        self.attached = False
        self.last_attach: AttachResult | None = None
        self.tracker: Tracker | None = None
        self.slot_data: dict[str, Any] = {}
        self.binding_requested = False
        self.last_status = ""
        self.game_task: asyncio.Task | None = None

    # ------------------------------------------------------------------ server

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect(game=self.game)

    @property
    def profile_key(self) -> str:
        return f"bj3_{self.team}_{self.slot}_profile"

    @property
    def baseline_key(self) -> str:
        return f"bj3_{self.team}_{self.slot}_baseline"

    @property
    def trap_index_key(self) -> str:  # reserved for Phase 4
        return f"bj3_{self.team}_{self.slot}_trap_index"

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            self.tracker = Tracker(self.server_locations, self.slot_data.get("starting_mode", 0),
                                   self.slot_data.get("goal", GOAL_SHARD_HUNT), self.slot_data.get("shard_required", 0))
            self.tracker.set_received(item.item for item in self.items_received)
            self.binding_requested = False
            self.last_status = ""
            # Read our keys back before sending anything (SPEC §7).
            self.stored_data.pop(self.profile_key, None)
            self.stored_data.pop(self.baseline_key, None)
            async_start(self.send_msgs([{"cmd": "Get", "keys": [self.profile_key, self.baseline_key,
                                                                  self.trap_index_key]}]), name="read binding")
        elif cmd == "ReceivedItems" and self.tracker is not None:
            self.tracker.set_received(item.item for item in self.items_received)
        elif cmd in ("Retrieved", "SetReply"):
            self._apply_stored_binding()

    def _apply_stored_binding(self) -> None:
        if self.tracker is None:
            return
        profile = self.stored_data.get(self.profile_key)
        baseline = self.stored_data.get(self.baseline_key)
        if isinstance(profile, str) and isinstance(baseline, dict) and self.tracker.bound_profile is None:
            self.tracker.apply_binding(profile, Baseline.from_json(baseline))
            logger.info(f"This seed is bound to Bejeweled 3 profile '{profile}'.")

    async def bind_profile(self) -> None:
        """First connect for this slot: store the active profile and its baseline (keeps an existing binding)."""
        assert self.tracker is not None
        name, baseline = self.tracker.proposed_binding()
        self.binding_requested = True
        await self.send_msgs([
            {"cmd": "Set", "key": self.profile_key, "default": name, "want_reply": True,
             "operations": [{"operation": "default", "value": None}]},
            {"cmd": "Set", "key": self.baseline_key, "default": baseline.to_json(), "want_reply": True,
             "operations": [{"operation": "default", "value": None}]},
        ])

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.tracker = None
        await super().disconnect(allow_autoreconnect)

    def make_gui(self):  # the kivy type only exists with the GUI
        ui = super().make_gui()
        ui.base_title = "Archipelago Bejeweled 3 Client"
        return ui

    # ------------------------------------------------------------------ game

    async def tick(self) -> float:
        """One iteration of the game loop. Returns how long to wait before the next one."""
        if not self.attached:
            await self.try_attach()
            return POLL_INTERVAL if self.attached else ATTACH_INTERVAL
        assert self.reader is not None
        if not self.reader.alive():
            logger.info("Bejeweled 3 was closed. Waiting for it to start again.")
            self.detach()
            return ATTACH_INTERVAL
        snapshot = self.reader.read()
        tracker = self.tracker
        if tracker is None:
            return POLL_INTERVAL
        tracker.update(snapshot)
        if tracker.needs_binding and not self.binding_requested and self.binding_known_empty():
            await self.bind_profile()
        to_send = tracker.evaluate(self.checked_locations)
        if to_send:
            await self.check_locations(to_send)
        for message in tracker.drain_messages():
            logger.info(message)
        if not self.finished_game and tracker.goal_reached():
            await self.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            self.finished_game = True
            logger.info("Goal complete!")
        status = tracker.status_line()
        if status != self.last_status:
            self.last_status = status
            logger.info(status)
        return POLL_INTERVAL

    def binding_known_empty(self) -> bool:
        """True once the server has answered our Get and holds no binding for this slot yet."""
        return (self.profile_key in self.stored_data and self.stored_data[self.profile_key] is None
                and self.baseline_key in self.stored_data and self.stored_data[self.baseline_key] is None)

    async def try_attach(self) -> None:
        if self.reader is None:
            try:
                self.reader = self.reader_factory()
            except Exception as error:  # e.g. not Windows
                self._report_attach(AttachResult(AttachStatus.NOT_RUNNING, str(error)))
                return
        try:
            result = await asyncio.get_running_loop().run_in_executor(None, self.reader.attach)
        except Exception as error:
            logger.debug("attach failed", exc_info=True)
            result = AttachResult(AttachStatus.NOT_RUNNING, f"Couldn't attach: {error}")
        self._report_attach(result)
        if result.status == AttachStatus.ATTACHED:
            self.attached = True
            if self.tracker is not None:
                self.tracker.reset_game_state()

    def _report_attach(self, result: AttachResult) -> None:
        if self.last_attach is None or result.status != self.last_attach.status:
            log = logger.warning if result.status in (AttachStatus.ACCESS_DENIED,
                                                       AttachStatus.UNSUPPORTED_VERSION) else logger.info
            log(result.detail or result.status.value)
        self.last_attach = result

    def detach(self) -> None:
        if self.reader is not None:
            self.reader.close()
        self.attached = False
        self.last_attach = None
        if self.tracker is not None:
            self.tracker.reset_game_state()

    def status_lines(self) -> list[str]:
        lines = [f"Game: {self.reader.build if self.reader and self.attached else 'not attached'}"]
        tracker = self.tracker
        if tracker is None:
            lines.append("Not connected to an Archipelago server.")
            return lines
        stable = tracker.stable
        if stable is not None:
            board = stable.board
            where = "menu" if board is None else (board.mode or board.rtti)
            level = f", level {board.level + 1}, score {board.score}" if board is not None else ""
            lines.append(f"Profile: {stable.profile_name} (bound: {tracker.bound_profile or 'not yet'}) | "
                         f"Now in: {where}{level}")
        if tracker.paused_reason:
            lines.append(f"Paused: {tracker.paused_reason}")
        lines.append(tracker.status_line())
        lines += [f"Held: {self.location_names.lookup_in_game(location)} - waiting for {missing}"
                  for location, missing in sorted(tracker.held.items())]
        return lines


def _default_reader() -> GameReader:
    from .game.reader import PymemReader
    return PymemReader()


async def game_loop(ctx: Bejeweled3Context) -> None:
    while not ctx.exit_event.is_set():
        try:
            delay = await ctx.tick()
        except Exception:
            logger.exception("Bejeweled 3 client error; retrying")
            ctx.detach()
            delay = ATTACH_INTERVAL
        await asyncio.sleep(delay)


async def main(args: Any) -> None:
    ctx = Bejeweled3Context(args.connect, args.password)
    ctx.auth = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    ctx.game_task = asyncio.create_task(game_loop(ctx), name="game loop")
    await ctx.exit_event.wait()
    ctx.detach()
    await ctx.shutdown()


def launch(*args: Sequence[str]) -> None:
    init_logging("Bejeweled3Client")
    parser = get_base_parser()
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    launch_args = handle_url_arg(parser.parse_args(args))
    colorama.just_fix_windows_console()
    asyncio.run(main(launch_args))
    colorama.deinit()


if __name__ == "__main__":
    launch(*sys.argv[1:])
