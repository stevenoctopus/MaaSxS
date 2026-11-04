"""Vendor Booth: buy General items (gold), refreshing for new ones, then
Vault items (Dawnium). Starts in the Vendor Booth, on any tab.

  General  (VendorBooth_General) {"discount": N}  buy each of the 9 items
           that is N% off or more (0 = every item).
           (VendorBooth_Refreshes) {"refreshes": R}  refreshes to have used
           today (refreshes already used today count). The current items are
           bought from first, then each refresh's.
  Vault    the Free reward is always claimed; (VendorBooth_Vault_<item>)
           {"buy": 1} buys that item up to its limit.

Buying is instant: a tile turns "Sold Out". Discounts are read from the
tilted "-N%" badge at a tile's top left (agent/badge.py).
"""
from dataclasses import dataclass

import numpy as np
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

import badge
from common import give_up, ok, settings_node, task_settings
from gui import say
from screen import hit, read_int, screenshot

# Top left of each tile of the 3x3 grid, row by row.
TILES = [(x0, y0) for y0 in (188, 470, 753) for x0 in (30, 260, 490)]
BADGE_W, BADGE_H = 75, 55

@dataclass
class VaultItem:
    tile: int     # index in TILES
    setting: str  # its settings node is VendorBooth_Vault_<setting> ({"buy": 1} buys it)
    name: str     # for the log
    limit: int    # purchase limit


FREE = VaultItem(0, "", "Free reward", 1)  # always claimed
VAULT = [
    VaultItem(1, "Stellatie", "Stellatie", 1),
    VaultItem(2, "DestinyFruit", "Destiny Fruit", 2),
    VaultItem(3, "Row2Left", "row 2, left", 1),
    VaultItem(4, "Row2Middle", "row 2, middle", 1),
    VaultItem(5, "RefinedOre", "Refined Ore", 1),
    VaultItem(6, "Row3Left", "row 3, left", 1),
    VaultItem(7, "Row3Middle", "row 3, middle", 1),
    VaultItem(8, "QuestScroll", "Quest Scroll", 1),
]
MAX_REFRESHES = 10


def log(context: Context, msg: str):
    say(context, "Vendor Booth", msg)


def sold_out(context: Context, tile: int, image=None) -> bool:
    x0, y0 = TILES[tile]
    return hit(context, "VendorBooth_SoldOut", image,
               {"VendorBooth_SoldOut": {"roi": [x0 + 10, y0 + 87, 180, 45]}})


def discount(context: Context, image, tile: int):
    """% off on a tile: 0 with no badge, None if there's a badge we can't read."""
    x0, y0 = TILES[tile]
    crop = image[y0 - 20:y0 - 20 + BADGE_H, x0 - 25:x0 - 25 + BADGE_W]
    b, r = crop[..., 0].astype(int), crop[..., 2].astype(int)
    if ((r > 200) & (r - b > 90)).sum() < 300:  # hardly any orange: no badge
        return 0
    text = badge.prep(crop)
    canvas = np.full_like(image, 255)
    canvas[20:20 + text.shape[0], 20:20 + text.shape[1]] = text
    return read_int(context, "VendorBooth_Discount", canvas, {
        "VendorBooth_Discount": {"roi": [10, 10, text.shape[1] + 20, text.shape[0] + 20]}})


def buy(context: Context, tile: int, limit: int, page: str) -> bool:
    """Tap a tile's price button until it's Sold Out (at most `limit` taps)."""
    x0, y0 = TILES[tile]
    for _ in range(limit):
        if sold_out(context, tile):
            return True
        context.run_task("VendorBooth_Buy", pipeline_override={
            "VendorBooth_Buy": {"target": [x0 + 30, y0 + 205, 140, 32]}})
        if not hit(context, page):  # a popup (e.g. not enough gold / Dawnium)
            return False
    return sold_out(context, tile)


def go_tab(context: Context, tab: str) -> bool:
    """Open a tab ("General" / "Vault"). Tabs open scrolled to the top."""
    page = f"VendorBooth_On{tab}"
    return hit(context, page) or ok(context.run_task(f"VendorBooth_Tab{tab}"))


# ---------------------------------------------------------------- General

def buy_page(context: Context, min_off: int) -> bool:
    image = screenshot(context)
    bought, skipped = [], []
    for tile in range(9):
        if sold_out(context, tile, image):
            continue
        off = discount(context, image, tile)
        if min_off > 0 and (off is None or off < min_off):
            skipped.append("?" if off is None else f"{off}%")
            continue
        if not buy(context, tile, 1, "VendorBooth_OnGeneral"):
            return give_up(context, "Vendor Booth", f"could not buy General item {tile + 1} (not enough gold?)")
        bought.append(f"{off}%" if off else "full price")
    msg = f"bought {len(bought)}"
    if bought:
        msg += f" ({', '.join(bought)})"
    if skipped:
        msg += f", skipped {len(skipped)} under {min_off}% off ({', '.join(skipped)})"
    log(context, msg)
    return True


def read_left(context: Context):
    return read_int(context, "VendorBooth_RefreshesLeft")


def general(context: Context, min_off: int, wanted: int) -> bool:
    if not go_tab(context, "General"):
        log(context, "could not open the General tab")
        return False
    left = read_left(context)
    if left is None:
        log(context, "could not read the refreshes left")
        return False
    used = MAX_REFRESHES - left
    todo = max(0, min(wanted, MAX_REFRESHES) - used)
    log(context, f"General: {used} refresh(es) used today, {todo} to do")
    if not buy_page(context, min_off):
        return False
    for n in range(todo):
        if context.tasker.stopping:
            log(context, "stop requested")
            return False
        context.run_task("VendorBooth_Refresh")
        now = read_left(context)
        if now is None or now >= left:
            return give_up(context, "Vendor Booth", "the refresh didn't go through (not enough gold?)")
        left = now
        log(context, f"refreshed ({n + 1}/{todo})")
        if not buy_page(context, min_off):
            return False
    return True


# ---------------------------------------------------------------- Vault

def vault(context: Context) -> bool:
    if not go_tab(context, "Vault"):
        log(context, "could not open the Vault tab")
        return False
    wanted = [item for item in VAULT
              if int(settings_node(context, f"VendorBooth_Vault_{item.setting}").get("buy", 0))]
    for item in [FREE] + wanted:
        if sold_out(context, item.tile):
            log(context, f"Vault: {item.name} already bought")
            continue
        if not buy(context, item.tile, item.limit, "VendorBooth_OnVault"):
            return give_up(context, "Vendor Booth", f"Vault: could not buy {item.name} (not enough Dawnium?)")
        log(context, f"Vault: bought {item.name}")
    return True


@AgentServer.custom_action("VendorBooth")
class VendorBooth(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        min_off = int(task_settings(argv).get("discount", 0))
        refreshes = int(settings_node(context, "VendorBooth_Refreshes").get("refreshes", 0))
        if not (general(context, min_off, refreshes) and vault(context)):
            return False
        log(context, "done")
        return True
