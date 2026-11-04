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
import json

import numpy as np
from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

import badge
from common import ok
from gui import say

# Top left of each tile of the 3x3 grid, row by row.
TILES = [(x0, y0) for y0 in (188, 470, 753) for x0 in (30, 260, 490)]
BADGE_W, BADGE_H = 75, 55

# Vault tiles after the Free one (tile 0): (node suffix, name, purchase limit).
VAULT = [
    ("Stellatie", "Stellatie", 1),
    ("DestinyFruit", "Destiny Fruit", 2),
    ("Row2Left", "row 2, left", 1),
    ("Row2Middle", "row 2, middle", 1),
    ("RefinedOre", "Refined Ore", 1),
    ("Row3Left", "row 3, left", 1),
    ("Row3Middle", "row 3, middle", 1),
    ("QuestScroll", "Quest Scroll", 1),
]
MAX_REFRESHES = 10


def log(context: Context, msg: str):
    say(context, "Vendor Booth", msg)


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def node_param(context: Context, node: str) -> dict:
    data = context.get_node_data(node) or {}
    param = data.get("action", {}).get("param", {}).get("custom_action_param") or {}
    return json.loads(param) if isinstance(param, str) else param


def hit(context: Context, node: str, image=None, override=None) -> bool:
    reco = context.run_recognition(node, screenshot(context) if image is None else image,
                                   pipeline_override=override or {})
    return bool(reco and reco.hit)


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
    reco = context.run_recognition("VendorBooth_Discount", canvas, pipeline_override={
        "VendorBooth_Discount": {"roi": [10, 10, text.shape[1] + 20, text.shape[0] + 20]}})
    if not (reco and reco.hit):
        return None
    digits = "".join(c for c in reco.best_result.text if c.isdigit())
    return int(digits) if digits else None


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
    """Open a tab ("General" / "Vault") with its list scrolled to the top."""
    page = f"VendorBooth_On{tab}"
    if not hit(context, page) and not ok(context.run_task(f"VendorBooth_Tab{tab}")):
        return False
    context.run_task("VendorBooth_ScrollTop")
    return hit(context, page)


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
            log(context, f"could not buy item {tile + 1} (not enough gold?)")
            return False
        bought.append(f"{off}%" if off else "full price")
    msg = f"bought {len(bought)}"
    if bought:
        msg += f" ({', '.join(bought)})"
    if skipped:
        msg += f", skipped {len(skipped)} under {min_off}% off ({', '.join(skipped)})"
    log(context, msg)
    return True


def read_left(context: Context):
    reco = context.run_recognition("VendorBooth_RefreshesLeft", screenshot(context))
    if reco and reco.hit:
        digits = "".join(c for c in reco.best_result.text if c.isdigit())
        return int(digits) if digits else None
    return None


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
            log(context, "the refresh didn't go through (not enough gold?)")
            return False
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
    wanted = [(i + 1, name, limit) for i, (key, name, limit) in enumerate(VAULT)
              if int(node_param(context, f"VendorBooth_Vault_{key}").get("buy", 0))]
    for tile, name, limit in [(0, "Free reward", 1)] + wanted:
        if sold_out(context, tile):
            log(context, f"Vault: {name} already bought")
            continue
        if not buy(context, tile, limit, "VendorBooth_OnVault"):
            log(context, f"Vault: could not buy {name} (not enough Dawnium?)")
            return False
        log(context, f"Vault: bought {name}")
    return True


@AgentServer.custom_action("VendorBooth")
class VendorBooth(CustomAction):
    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        min_off = int(json.loads(argv.custom_action_param or "{}").get("discount", 0))
        refreshes = int(node_param(context, "VendorBooth_Refreshes").get("refreshes", 0))
        if not (general(context, min_off, refreshes) and vault(context)):
            return False
        log(context, "done")
        return True
