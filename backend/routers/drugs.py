"""药品批量导入接口（POST /api/drugs/import）。

上传 CSV（列：药品编码/通用名/商品名/规格/剂型/单位/单价/医保类别/库存数量），
服务端逐行校验，返回成功 N 条、失败 M 条及错误明细。
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from main import get_connection
from security import require_permission
from services.drug_import import import_drugs_csv

router = APIRouter(prefix="/api", tags=["药品"])


@router.post("/drugs/import")
async def import_drugs(
    file: UploadFile = File(...),
    user: dict = Depends(require_permission("pharmacy:stock_in")),
) -> dict:
    """药品批量导入（药师/管理员）。"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")

    conn = get_connection()
    try:
        return import_drugs_csv(conn, data)
    finally:
        conn.close()
