"""Offer-level enrichment: MOQ, price ladder, extra photos, supplier member id."""
from __future__ import annotations

from . import cli1688


def _qty_text(o: dict) -> str:
    qty = o.get("minOrderQty")
    unit = o.get("unitName") or ""
    return f"{qty}{unit}" if qty not in (None, "", 0) else ""


def _tiers_text(o: dict) -> str:
    tiers = o.get("priceTiers") or []
    if len(tiers) < 2:
        return ""
    parts = []
    for t in tiers[:4]:
        qty = t.get("minQty")
        price = t.get("price")
        if qty is None or price is None:
            continue
        parts.append(f"{qty}件¥{price}")
    return " / ".join(parts)


def attach(rows: list[dict], limit: int = 10) -> None:
    """Fill rows[*].offers[*] from offer detail.

    The main offer of every row always gets enriched first (so the supplier sheet
    has MOQ/price), then the remaining budget goes to secondary offers.
    """
    pairs: list[tuple[dict, dict]] = []
    seen: set[str] = set()
    for row in rows:
        offers = row.get("offers") or []
        if offers and offers[0].get("offer_id") and len(pairs) < limit:
            pairs.append((row, offers[0]))
            seen.add(offers[0]["offer_id"])
    for row in rows:
        for offer in (row.get("offers") or [])[1:]:
            if len(pairs) >= limit:
                break
            oid = offer.get("offer_id")
            if oid and oid not in seen:
                pairs.append((row, offer))
                seen.add(oid)
    if not pairs:
        return
    details = cli1688.offer_details([o["offer_id"] for _, o in pairs])
    for row, offer in pairs:
        d = details.get(offer["offer_id"])
        if not d:
            continue
        offer["min_order"] = offer.get("min_order") or _qty_text(d)
        if d.get("priceRange"):
            offer["price"] = str(d["priceRange"]).replace("￥", "¥")
        offer["tiers"] = _tiers_text(d)
        if d.get("url") and not offer.get("url"):
            offer["url"] = d["url"]
        supplier = d.get("supplier") or {}
        if not row.get("member_id"):
            row["member_id"] = supplier.get("memberId") or ""
        if not row.get("shop_url"):
            row["shop_url"] = supplier.get("shopUrl") or ""
