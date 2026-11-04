"""Reading the screen: screenshots, recognition hits, and one rule for
turning OCR text into numbers.

Numbers: the first run of digits in the text ("5", "x5", "Attempt 3/5" -> 5,
5, 3). Fractions: the first "N/M" ("Daily Purchase Limit: 2/6" -> (2, 6)).

Every reader takes an optional `image`, to read several things off one
screenshot; without it, it takes a fresh one.
"""
import json
import re

from maa.context import Context

NUMBER_RE = re.compile(r"\d+")
FRACTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def screenshot(context: Context):
    return context.tasker.controller.post_screencap().wait().get()


def recognize(context: Context, node: str, image=None, override=None):
    """Run recognition node `node` (with an optional pipeline override for
    it); the result if it hit, else None."""
    reco = context.run_recognition(node, screenshot(context) if image is None else image,
                                   pipeline_override=override or {})
    return reco if reco and reco.hit else None


def hit(context: Context, node: str, image=None, override=None) -> bool:
    return recognize(context, node, image, override) is not None


def parse_int(text):
    m = NUMBER_RE.search(text or "")
    return int(m.group()) if m else None


def parse_fraction(text):
    m = FRACTION_RE.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def read_int(context: Context, node: str, image=None, override=None):
    """The number in OCR node `node`'s text, or None."""
    reco = recognize(context, node, image, override)
    return parse_int(reco.best_result.text) if reco else None


def read_fraction(context: Context, node: str, image=None, override=None):
    """The "N/M" in OCR node `node`'s text as (N, M), or None."""
    reco = recognize(context, node, image, override)
    return parse_fraction(reco.best_result.text) if reco else None


def node_param(context: Context, node: str) -> dict:
    """The custom_action_param of another node, with the task's overrides
    (how a task reads options stored on its settings nodes)."""
    data = context.get_node_data(node) or {}
    param = data.get("action", {}).get("param", {}).get("custom_action_param") or {}
    return json.loads(param) if isinstance(param, str) else param
