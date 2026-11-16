"""Image path: photo -> 1688 image search (拍立淘) -> supplier rows.

The bundled `1688 image-search` command still targets the retired
`s.1688.com/youyuan/index.htm` upload page and fails with
STABLE_LOCATOR_NOT_FOUND, so this module drives the current upload widget on the
offer-search page itself (see scripts/imgsearch.cjs).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import cli1688, offers as offer_lib

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "imgsearch.cjs"


def _years(text: str):
    m = re.search(r"(\d+)\s*年", text or "")
    return int(m.group(1)) if m else ""


def _price(text: str) -> str:
    m = re.search(r"[¥￥]\s*([\d.]+)", text or "")
    return m.group(1) if m else ""


def _moq(text: str) -> str:
    m = re.search(r"(\d+)\s*件起批", text or "")
    return m.group(1) if m else ""


def search(image_path, max_results: int = 40) -> dict:
    proc = subprocess.run(
        [cli1688.NODE, str(SCRIPT), str(image_path), "--max", str(max_results)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
    )
    data = cli1688._parse_json(proc.stdout)
    if not data:
        raise cli1688.CliError("IMAGE_SEARCH_FAILED", (proc.stderr or proc.stdout or "")[:400])
    if not data.get("ok"):
        raise cli1688.CliError("IMAGE_SEARCH_FAILED", data.get("error") or "unknown failure")
    return data


def group_by_supplier(rows, per_supplier: int = 4, offer_enrich: int = 10) -> list[dict]:
    order: list[str] = []
    groups: dict[str, dict] = {}
    for r in rows:
        name = (r.get("supplierName") or "").strip()
        if not name:
            continue
        if name not in groups:
            order.append(name)
            groups[name] = {
                "name": name,
                "province": "",
                "city": "",
                "address": "",
                "years": _years(r.get("serviceYears")),
                "repeat_rate": r.get("repurchaseRate") or "",
                "response_rate": "",
                "kind": "供应商",
                "factory_tag": "",
                "score": "",
                "products": "",
                "shop_url": "",
                "card_url": "",
                "member_id": "",
                "employees": "",
                "established": "",
                "offers": [],
                "source": "image",
            }
        g = groups[name]
        if len(g["offers"]) < per_supplier:
            price_text = r.get("price") or ""
            g["offers"].append({
                "offer_id": str(r.get("offerId") or ""),
                "title": (r.get("title") or "").strip(),
                "url": (f"https://detail.1688.com/offer/{r['offerId']}.html" if r.get("offerId") else ""),
                "price": f"¥{_price(price_text)}" if _price(price_text) else price_text,
                "unit": "",
                "image": r.get("image") or "",
                "min_order": _moq(price_text),
            })
    out = [groups[n] for n in order]
    if offer_enrich:
        offer_lib.attach(out, offer_enrich)
    return out
