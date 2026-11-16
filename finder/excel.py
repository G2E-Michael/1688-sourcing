"""Write supplier rows to an .xlsx with embedded product photos."""
from __future__ import annotations

import io
from pathlib import Path

import requests
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36")

HEAD_FILL = PatternFill("solid", fgColor="FFF3E0")
HEAD_FONT = Font(bold=True, color="7A3E00")
THIN = Side(style="thin", color="E0E0E0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _download(url: str, dest: Path) -> bool:
    if not url:
        return False
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Referer": "https://s.1688.com/"}, timeout=25)
        if r.status_code != 200 or not r.content:
            return False
        from PIL import Image

        im = Image.open(io.BytesIO(r.content))
        im = im.convert("RGB")
        im.thumbnail((300, 300))
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, "JPEG", quality=88)
        return True
    except Exception:
        return False


def _style_header(ws, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"


def _link(cell, url: str, text: str | None = None) -> None:
    if not url:
        cell.value = text or ""
        return
    cell.value = text or url
    cell.hyperlink = url
    cell.font = Font(color="0563C1", underline="single")


def write(rows: list[dict], out_path: Path, title: str = "1688 供应商", download: bool = True) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img_dir = out_path.with_name(out_path.stem + "_images")

    wb = Workbook()
    ws = wb.active
    ws.title = "供应商"

    headers = ["序号", "主图", "供应商名称", "省份", "城市", "入驻年限", "回头率%", "响应率%",
               "类型", "工厂标签", "综合评分", "主营产品", "主推产品", "价格", "起批",
               "产品链接", "店铺链接", "工厂名片"]
    widths = [6, 15, 34, 8, 10, 9, 9, 9, 10, 18, 9, 26, 34, 10, 8, 28, 26, 26]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        ws.cell(row=1, column=i, value=h)
        ws.column_dimensions[get_column_letter(i)].width = w
    _style_header(ws, len(headers))

    for idx, row in enumerate(rows, start=1):
        r = idx + 1
        offers = row.get("offers") or []
        main = offers[0] if offers else {}
        ws.cell(row=r, column=1, value=idx)
        ws.cell(row=r, column=3, value=row.get("name", ""))
        ws.cell(row=r, column=4, value=row.get("province", ""))
        ws.cell(row=r, column=5, value=row.get("city", ""))
        ws.cell(row=r, column=6, value=row.get("years", ""))
        ws.cell(row=r, column=7, value=row.get("repeat_rate", ""))
        ws.cell(row=r, column=8, value=row.get("response_rate", ""))
        ws.cell(row=r, column=9, value=row.get("kind", ""))
        ws.cell(row=r, column=10, value=row.get("factory_tag", ""))
        ws.cell(row=r, column=11, value=row.get("score", ""))
        ws.cell(row=r, column=12, value=row.get("products", ""))
        ws.cell(row=r, column=13, value=main.get("title", ""))
        ws.cell(row=r, column=14, value=main.get("price") or "")
        ws.cell(row=r, column=15, value=main.get("min_order") or "")
        _link(ws.cell(row=r, column=16), main.get("url", ""), "打开产品")
        _link(ws.cell(row=r, column=17), row.get("shop_url", ""), "进店铺")
        _link(ws.cell(row=r, column=18), row.get("card_url", ""), "看工厂")

        if download and main.get("image"):
            dest = img_dir / f"{idx:03d}.jpg"
            if _download(main["image"], dest):
                try:
                    pic = XLImage(str(dest))
                    pic.width, pic.height = 92, 92
                    ws.add_image(pic, f"B{r}")
                except Exception:
                    pass
        ws.row_dimensions[r].height = 72
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = BORDER
            if c not in (16, 17, 18):
                cell.alignment = Alignment(vertical="center", wrap_text=c in (3, 12, 13))

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(len(rows) + 1, 2)}"

    # ---- product detail sheet ----
    ws2 = wb.create_sheet("产品明细")
    h2 = ["序号", "供应商", "产品标题", "价格", "起批", "阶梯价", "产品图", "产品链接", "offerId"]
    w2 = [6, 30, 46, 10, 8, 24, 15, 26, 16]
    for i, (h, w) in enumerate(zip(h2, w2), start=1):
        ws2.cell(row=1, column=i, value=h)
        ws2.column_dimensions[get_column_letter(i)].width = w
    _style_header(ws2, len(h2))

    n = 0
    for row in rows:
        for offer in row.get("offers") or []:
            n += 1
            r = n + 1
            ws2.cell(row=r, column=1, value=n)
            ws2.cell(row=r, column=2, value=row.get("name", ""))
            ws2.cell(row=r, column=3, value=offer.get("title", ""))
            ws2.cell(row=r, column=4, value=offer.get("price", ""))
            ws2.cell(row=r, column=5, value=offer.get("min_order") or "")
            ws2.cell(row=r, column=6, value=offer.get("tiers") or "")
            _link(ws2.cell(row=r, column=8), offer.get("url", ""), "打开")
            ws2.cell(row=r, column=9, value=str(offer.get("offer_id") or ""))
            if download and offer.get("image"):
                dest = img_dir / f"o{n:03d}.jpg"
                if _download(offer["image"], dest):
                    try:
                        pic = XLImage(str(dest))
                        pic.width, pic.height = 92, 92
                        ws2.add_image(pic, f"G{r}")
                    except Exception:
                        pass
            ws2.row_dimensions[r].height = 72
            for c in range(1, len(h2) + 1):
                cell = ws2.cell(row=r, column=c)
                cell.border = BORDER
                if c != 8:
                    cell.alignment = Alignment(vertical="center", wrap_text=c in (2, 3))

    ws2.auto_filter.ref = f"A1:{get_column_letter(len(h2))}{max(n + 1, 2)}"
    wb.save(out_path)
    return out_path
