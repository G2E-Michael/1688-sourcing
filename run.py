#!/usr/bin/env python
"""1688 supplier finder — keyword or image -> suppliers with photos -> Excel."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from finder import cli1688, excel as xl, image as img, keyword as kw  # noqa: E402


def _default_out(tag: str) -> Path:
    import datetime as _dt

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in tag if c not in '\\/:*?"<>|').strip() or "1688"
    return Path.cwd() / "out" / f"1688_{safe}_{stamp}.xlsx"


def cmd_check(_args) -> int:
    info = cli1688.doctor()
    print(f"node          : {cli1688.NODE}")
    print(f"1688 cli      : {cli1688.cli_js()}")
    print(f"chrome        : {cli1688.chrome_path() or '(not found)'}")
    print(f"profile       : {cli1688.PROFILE_DIR}")
    who = cli1688.whoami()
    if who.get("loggedIn"):
        print(f"login         : OK  {who.get('nick')} (memberId={who.get('memberId')})")
    else:
        print("login         : NOT LOGGED IN -> run:  1688 login --headed")
    checks = {c["name"]: c for c in info.get("checks", [])}
    for name in ("browser launch", "session", "profile dir"):
        c = checks.get(name)
        if c:
            print(f"{name:<14}: {c['status']}  {c['message']}")
    return 0 if who.get("loggedIn") else 1


def cmd_keyword(args) -> int:
    out = Path(args.out) if args.out else _default_out(args.keywords[0])
    data = kw.search(
        args.keywords,
        max_per=args.max,
        factory_only=args.factory_only,
        province=args.province,
        city=args.city,
        min_years=args.min_years,
        min_repeat_rate=args.min_repeat_rate,
        offer_enrich=0 if args.no_offer_detail else args.offers,
    )
    rows = data["rows"][: args.top]
    print(f"matched suppliers: {len(rows)} (before filter {data.get('total_before')})")
    if args.enrich:
        kw.enrich(rows[: args.enrich])
    written = xl.write(rows, out, title="1688 供应商", download=not args.no_images)
    print(f"excel: {written}")
    return 0


def cmd_image(args) -> int:
    src = Path(args.image).expanduser()
    if not src.exists():
        print(f"image not found: {src}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else _default_out(src.stem)
    data = img.search(src, max_results=args.max)
    rows = img.group_by_supplier(
        data["rows"],
        offer_enrich=0 if args.no_offer_detail else args.offers,
    )[: args.top]
    print(f"imageId: {data.get('imageId')}  offers: {len(data['rows'])}  suppliers: {len(rows)}")
    for row in rows:
        if not row.get("years"):
            row["years"] = ""
    if args.enrich:
        kw.enrich(rows[: args.enrich])
    written = xl.write(rows, out, title="1688 图搜结果", download=not args.no_images)
    print(f"excel: {written}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="1688-supplier-finder", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verify environment and login state")
    c.set_defaults(func=cmd_check)

    k = sub.add_parser("keyword", help="search suppliers by keyword")
    k.add_argument("keywords", nargs="+")
    k.add_argument("--max", type=int, default=20, help="suppliers per keyword (default 20)")
    k.add_argument("--top", type=int, default=20, help="keep top N rows (default 20)")
    k.add_argument("--factory-only", action="store_true", default=True)
    k.add_argument("--include-traders", action="store_true", help="also keep non-factory suppliers")
    k.add_argument("--province", default=None)
    k.add_argument("--city", default=None)
    k.add_argument("--min-years", type=int, default=None)
    k.add_argument("--min-repeat-rate", type=float, default=None)
    k.add_argument("--enrich", type=int, default=0, help="fetch factory card for top N suppliers")
    k.add_argument("--offers", type=int, default=12, help="fetch offer detail (MOQ/price ladder) for top N offers")
    k.add_argument("--no-offer-detail", action="store_true", help="skip offer detail requests (faster)")
    k.add_argument("--out", default=None)
    k.add_argument("--no-images", action="store_true")
    k.set_defaults(func=cmd_keyword)

    i = sub.add_parser("image", help="search by photo (local file or URL downloaded beforehand)")
    i.add_argument("image")
    i.add_argument("--max", type=int, default=40, help="max offers to capture (default 40)")
    i.add_argument("--top", type=int, default=20, help="keep top N suppliers (default 20)")
    i.add_argument("--offers", type=int, default=12, help="fetch offer detail (MOQ/price ladder) for top N offers")
    i.add_argument("--enrich", type=int, default=0, help="fetch factory card for top N suppliers (slower)")
    i.add_argument("--no-offer-detail", action="store_true", help="skip offer detail requests (faster)")
    i.add_argument("--out", default=None)
    i.add_argument("--no-images", action="store_true")
    i.set_defaults(func=cmd_image)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "include_traders", False):
        args.factory_only = False
    try:
        return args.func(args)
    except cli1688.CliError as e:
        print(f"[1688-cli] {e.code}: {e}", file=sys.stderr)
        if e.code in ("NOT_LOGGED_IN", "SESSION_EXPIRED"):
            print("run:  1688 login --headed", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
