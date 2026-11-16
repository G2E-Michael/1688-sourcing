"""Keyword path: 1688 company search -> normalised supplier rows."""
from __future__ import annotations

import time

from . import cli1688, offers as offer_lib


def _fmt_rate(value):
    if value is None or value == "":
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f <= 1.0:
        return round(f * 100, 1)
    return round(f, 1)


def _factory_kind(factory: dict) -> str:
    if factory.get("superFactory") or factory.get("shiliFactory"):
        return "实力工厂"
    if factory.get("isFactory"):
        return "工厂"
    if factory.get("shiliCompany"):
        return "实力商家"
    return "供应商"


def _factory_tags(factory: dict) -> str:
    tags = []
    if factory.get("superFactory"):
        tags.append("超级工厂")
    if factory.get("factoryInspection"):
        tags.append("验厂")
    if factory.get("businessInspection"):
        tags.append("深度验商")
    if factory.get("trust"):
        tags.append("诚信通")
    level = str(factory.get("factoryLevel") or "")
    if level and "无" not in level:
        tags.append(level)
    return " / ".join(tags)


def normalize(item: dict) -> dict | None:
    s = item.get("supplier") or {}
    name = (s.get("companyName") or "").strip()
    if not name:
        return None
    factory = s.get("factory") or {}
    tp = s.get("tp") or {}
    service = s.get("service") or {}
    loc = s.get("location") or {}
    offers = []
    for o in (s.get("offersPreview") or []):
        oid = str(o.get("offerId") or "")
        offers.append({
            "offer_id": oid,
            "title": (o.get("title") or "").strip(),
            "url": o.get("url") or (f"https://detail.1688.com/offer/{oid}.html" if oid else ""),
            "price": ((o.get("price") or {}).get("text") or "").strip(),
            "unit": o.get("unit") or "",
            "image": o.get("image") or "",
            "sale_qty": o.get("saleQuantity") or o.get("quantitySumMonth") or "",
        })
    years = tp.get("serviceYears")
    if isinstance(years, str):
        import re

        m = re.search(r"(\d+)", years)
        years = int(m.group(1)) if m else ""
    return {
        "name": name,
        "province": loc.get("province") or "",
        "city": loc.get("city") or "",
        "address": loc.get("address") or "",
        "years": years if years is not None else "",
        "repeat_rate": _fmt_rate(service.get("repeatRate")),
        "response_rate": _fmt_rate(service.get("wwResponseRate")),
        "kind": _factory_kind(factory),
        "factory_tag": _factory_tags(factory),
        "score": item.get("score") if item.get("score") is not None else "",
        "products": (s.get("productionService") or "").strip(),
        "shop_url": s.get("shopUrl") or "",
        "card_url": s.get("factoryCardUrl") or "",
        "member_id": s.get("memberId") or "",
        "employees": "",
        "established": "",
        "offers": offers,
        "source": "keyword",
    }


def search(keywords, max_per=20, factory_only=True, province=None, city=None,
           min_years=None, min_repeat_rate=None, offer_enrich: int = 10) -> dict:
    args = ["supplier", "search", *keywords, "--max", str(max_per)]
    if factory_only:
        args.append("--factory-only")
    if province:
        args += ["--province", province]
    if city:
        args += ["--city", city]
    if min_years:
        args += ["--min-years", str(min_years)]
    if min_repeat_rate:
        args += ["--min-repeat-rate", str(min_repeat_rate)]
    data = cli1688.run_json(args, timeout=600)
    rows = [r for r in (normalize(it) for it in data.get("items") or []) if r]
    if offer_enrich:
        offer_lib.attach(rows, offer_enrich)
    return {"rows": rows, "total_before": data.get("totalBeforeFilter") or data.get("total") or len(rows)}


def _split_region(address: str) -> tuple[str, str]:
    import re

    if not address:
        return "", ""
    province = ""
    m = re.match(r"(.{2,4}?(?:省|自治区))", address)
    if m:
        province = m.group(1)
    else:
        m = re.match(r"(北京市|上海市|天津市|重庆市)", address)
        if m:
            province = m.group(1)
    city = ""
    rest = address[len(province):] if province else address
    m = re.match(r"(.{2,6}?(?:市|自治州|地区|盟))", rest)
    if m:
        city = m.group(1)
    return province, city


def enrich(rows, pause: float = 3.0) -> None:
    """Fill factory-card details; accepts rows without memberId by inspecting their first offer."""
    for row in rows:
        target = row.get("member_id") or ((row.get("offers") or [{}])[0].get("offer_id") or "")
        if not target:
            continue
        try:
            data = cli1688.run_json(["supplier", "inspect", str(target)], timeout=240)
        except cli1688.CliError:
            continue
        factory = data.get("factory") or {}
        supplier = data.get("supplier") or {}
        target_info = data.get("target") or {}
        row["member_id"] = target_info.get("memberId") or supplier.get("memberId") or row.get("member_id", "")
        row["employees"] = factory.get("employeeScale") or factory.get("workerCount") or ""
        row["established"] = factory.get("establishedAtText") or ""
        row["address"] = factory.get("address") or row.get("address", "")
        row["products"] = row.get("products") or (factory.get("productionService") or "")
        row["shop_url"] = row.get("shop_url") or (supplier.get("shopUrl") or "")
        if not row.get("card_url") and row["member_id"]:
            row["card_url"] = f"https://sale.1688.com/factory/card.html?memberId={row['member_id']}"
        if factory.get("tpYears"):
            row["years"] = factory["tpYears"]
        prov, city = _split_region(row.get("address", ""))
        if prov and not row.get("province"):
            row["province"] = prov
        if city and not row.get("city"):
            row["city"] = city
        loc = str(factory.get("location") or "")
        if loc and not row.get("city"):
            row["city"] = loc
        if not row.get("kind") or row.get("kind") == "供应商":
            row["kind"] = "工厂" if factory.get("isFactory") else (row.get("kind") or "供应商")
        if not row.get("factory_tag") and factory.get("isFactory"):
            row["factory_tag"] = "工厂名片已核" + (" / 验厂" if factory.get("thirdPartyAuthProvider") else "")
        time.sleep(pause)
