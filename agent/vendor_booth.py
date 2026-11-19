"""Vendor Booth: buy General items (gold), refreshing for new ones, then
Vault items (Dawnium). Starts in the Vendor Booth, on any tab.

  General  (VendorBooth_General) {"discount": N}  buy each of the 9 items
           that is N% off or more (0 = every item).
           (VendorBooth_Refreshes) {"refreshes": R}  refreshes to have used
           today (refreshes already used today count). The current items are
           bought from first, then each refresh's.
  Vault    the Free reward is always claimed; (VendorBooth_Vault_<item>)
           {"vault_<item>": 1} buys that item up to its limit.

Buying is instant: a tile turns "Sold Out". Discounts are read from the
tilted "-N%" badge at a tile's top left (agent/badge.py).
"""
from dataclasses import dataclass

import numpy as np
from maa.context import Context

import badge
from common import ok
from screen import hit, read_int, screenshot
from task import Task, task

# Top left of each tile of the 3x3 grid, row by row.
TILES = [(x0, y0) for y0 in (188, 470, 753) for x0 in (30, 260, 490)]
BADGE_W, BADGE_H = 75, 55

@dataclass
class VaultItem:
    tile: int     # index in TILES
    setting: str  # its setting (1 buys it), on its node VendorBooth_Vault_<Item>
    name: str     # for the log
    limit: int    # purchase limit


FREE = VaultItem(0, "", "Free reward", 1)  # always claimed
VAULT = [
    VaultItem(1, "vault_stellatie", "row 1, middle", 1),  # was Stellatie; changes
    VaultItem(2, "vault_destiny_fruit", "Destiny Fruit", 2),
    VaultItem(3, "vault_row2_left", "row 2, left", 1),
    VaultItem(4, "vault_row2_middle", "row 2, middle", 1),
    VaultItem(5, "vault_refined_ore", "Refined Ore", 1),
    VaultItem(6, "vault_row3_left", "row 3, left", 1),
    VaultItem(7, "vault_row3_middle", "row 3, middle", 1),
    VaultItem(8, "vault_quest_scroll", "Quest Scroll", 1),
]
MAX_REFRESHES = 10


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

def buy_page(t: Task, min_off: int):
    image = screenshot(t.c)
    bought, skipped = [], []
    for tile in range(9):
        if sold_out(t.c, tile, image):
            continue
        off = discount(t.c, image, tile)
        if min_off > 0 and (off is None or off < min_off):
            skipped.append("?" if off is None else f"{off}%")
            continue
        if not buy(t.c, tile, 1, "VendorBooth_OnGeneral"):
            t.give_up(f"could not buy General item {tile + 1} (not enough gold?)")
        bought.append(f"{off}%" if off else "full price")
    msg = f"bought {len(bought)}"
    if bought:
        msg += f" ({', '.join(bought)})"
    if skipped:
        msg += f", skipped {len(skipped)} under {min_off}% off ({', '.join(skipped)})"
    t.log(msg)


def read_left(context: Context):
    return read_int(context, "VendorBooth_RefreshesLeft")


def general(t: Task, min_off: int, wanted: int):
    if not go_tab(t.c, "General"):
        t.fail("could not open the General tab")
    left = t.need(read_left(t.c), "could not read the refreshes left")
    used = MAX_REFRESHES - left
    todo = max(0, min(wanted, MAX_REFRESHES) - used)
    t.log(f"General: {used} refresh(es) used today, {todo} to do")
    buy_page(t, min_off)
    for n in range(todo):
        t.check()
        t.run("VendorBooth_Refresh")
        now = read_left(t.c)
        if now is None or now >= left:
            t.give_up("the refresh didn't go through (not enough gold?)")
        left = now
        t.log(f"refreshed ({n + 1}/{todo})")
        buy_page(t, min_off)


# ---------------------------------------------------------------- Vault

def vault(t: Task):
    if not go_tab(t.c, "Vault"):
        t.fail("could not open the Vault tab")
    wanted = [item for item in VAULT if t.settings[item.setting]]
    for item in [FREE] + wanted:
        if sold_out(t.c, item.tile):
            t.log(f"Vault: {item.name} already bought")
            continue
        if not buy(t.c, item.tile, item.limit, "VendorBooth_OnVault"):
            t.give_up(f"Vault: could not buy {item.name} (not enough Dawnium?)")
        t.log(f"Vault: bought {item.name}")


@task("VendorBooth", "Vendor Booth")
def vendor_booth(t: Task):
    general(t, t.settings["discount"], t.settings["refreshes"])
    vault(t)
    t.log("done")
