# -*- coding: utf-8 -*-
"""从《药品数据.xlsx》（湖南省医保药品目录）生成演示用药品导入 CSV。

输出：backend/data/drugs_import_demo.csv（UTF-8 中文表头）
- 约 100 条合法数据（通用名/剂型/医保类别取自真实目录，规格/单价/库存合成）
- 5 条刻意构造的"脏数据"，用于演示服务端校验与错误报告（错误行不入库）

CSV 列：药品编码,通用名,商品名,规格,剂型,单位,单价(元),医保类别,库存数量
"""
import csv
import random
import sys
from pathlib import Path

import openpyxl

BASE = Path(__file__).resolve().parent
XLSX = Path(r"E:\HIS\药品数据.xlsx")
OUT = BASE / "data" / "drugs_import_demo.csv"

random.seed(42)

UNITS = {"胶囊": "盒", "片剂": "盒", "注射剂": "支", "口服液体剂": "瓶",
         "滴眼剂": "支", "滴耳剂": "支", "滴鼻剂": "支", "软膏剂": "支",
         "散剂": "盒", "颗粒剂": "盒", "喷雾剂": "支", "外用液体剂": "瓶"}

SPEC_BY_FORM = {
    "胶囊": ["0.25g*24粒", "0.5g*12粒", "0.125g*20粒"],
    "片剂": ["10mg*24片", "0.3g*20片", "25mg*30片"],
    "注射剂": ["2ml:0.1g*10支", "5ml:0.25g*5支", "100ml*1瓶"],
    "口服液体剂": ["10ml*10支", "100ml*1瓶", "15ml*6支"],
    "滴眼剂": ["5ml*1支", "8ml*1支"],
    "滴耳剂": ["8ml*1支"], "滴鼻剂": ["10ml*1支"],
    "软膏剂": ["10g*1支", "15g*1支"], "散剂": ["3g*10袋"],
    "颗粒剂": ["5g*12袋"], "喷雾剂": ["20ml*1瓶"], "外用液体剂": ["100ml*1瓶"],
}


def collect_rows():
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb["Sheet1"]
    rows = []
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue  # 跳过表头
        code, name, form = r[7], r[8], r[9]
        trade = r[19]
        ins = r[28] if len(r) > 28 else None
        if not name or not form:
            continue
        rows.append((code, name, form, trade, ins))
        if len(rows) >= 20000:
            break
    wb.close()
    return rows


def main():
    rows = collect_rows()
    if not rows:
        print("未读取到数据，请检查 药品数据.xlsx 路径")
        sys.exit(1)

    # 过滤医院制剂（名字含"湘雅"），按编码去重后每 N 条取 1 得到约 100 条
    picked = [r for r in rows if "湘雅" not in str(r[1])]
    seen = set()
    uniq = []
    for r in picked:
        code = r[0]
        if code and code in seen:
            continue
        seen.add(code)
        uniq.append(r)
    step = max(1, len(uniq) // 100)
    sample = uniq[::step][:100]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = ["药品编码", "通用名", "商品名", "规格", "剂型", "单位", "单价", "医保类别", "库存数量"]
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, (code, name, form, trade, ins) in enumerate(sample):
            insurance = ins if ins in ("甲类", "乙类") else "乙类"
            unit = UNITS.get(str(form), "盒")
            spec = random.choice(SPEC_BY_FORM.get(str(form), ["10mg*10片"]))
            price = round(random.uniform(3, 80), 2)
            qty = random.randint(20, 500)
            w.writerow([str(code or f"D{20000 + i}"), name, trade or "", spec,
                        form, unit, f"{price:.2f}", insurance, qty])

        # 5 条脏数据（故意破坏，演示校验与错误报告）
        w.writerow(["", "缺编码的药品", "某品牌", "0.1g*20片", "片剂", "盒", "12.00", "乙类", 100])
        w.writerow(["D999991", "缺规格的药品", "", "", "胶囊", "盒", "15.50", "乙类", 80])
        w.writerow(["D999992", "非法单价的药品", "", "5ml*10", "口服液体剂", "瓶", "abc", "乙类", 60])
        w.writerow(["D999993", "非法医保类别", "", "10mg*14", "片剂", "盒", "9.90", "自费类", 40])
        w.writerow(["D999994", "非法库存数量", "", "0.5g*10", "片剂", "盒", "6.60", "甲类", "许多"])
        if sample:
            first = sample[0]
            w.writerow([str(first[0]), first[1] + "(重复)", "", "10mg*10片", "片剂", "盒", "8.80", "乙类", 30])

    print(f"已生成 {OUT}")
    print(f"合法 {len(sample)} 条 + 脏数据 5 条")
    with open(OUT, encoding="utf-8-sig") as f:
        for i, line in enumerate(f):
            if i < 3:
                print("  ", line.rstrip())


if __name__ == "__main__":
    main()
