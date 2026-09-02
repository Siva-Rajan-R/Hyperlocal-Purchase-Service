import os
import json
from datetime import datetime, timezone
import redis.asyncio as aioredis
from icecream import ic
from ..main import AsyncInventoryLocalSession
from ..repos.purchase_repo import PurchaseRepo
from schemas.v1.purchase_schemas.request_schema import GetPurchaseByShopIdSchema
from helpers.export_helper import generate_csv_bytes, generate_xlsx_bytes
from integrations.utility_service import upload_export_file
from helpers.emit_notification import emit_notification

REDIS_URL = os.getenv("PLATFORM_REDIS_URL") or "redis://localhost:6379"

async def process_purchase_export(payload: dict) -> dict:
    job_id = payload.get("job_id")
    shop_id = payload.get("shop_id")
    from_record = int(payload.get("from_record", 1))
    to_record = int(payload.get("to_record", 100))
    fmt = str(payload.get("format", "csv")).lower()
    query = payload.get("query")
    from_date = payload.get("from_date")
    to_date = payload.get("to_date")
    user_id = payload.get("user_id")
    status = payload.get("status")
    supplier_id = payload.get("supplier_id")

    limit = max(to_record - from_record + 1, 1)
    offset = from_record

    redis_client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    
    # 1. Update status to IN_PROGRESS
    if job_id:
        await redis_client.set(
            f"EXPORT_JOB:{job_id}",
            json.dumps({
                "job_id": job_id,
                "entity": "PURCHASE",
                "status": "IN_PROGRESS",
                "params": payload,
                "started_at": datetime.now(timezone.utc).isoformat()
            }),
            ex=86400
        )

    try:
        # 2. Fetch Purchases
        async with AsyncPurchaseLocalSession() as session:
            repo = PurchaseRepo(session=session)
            fetch_schema = GetPurchaseByShopIdSchema(
                shop_id=shop_id,
                query=query or "",
                limit=limit,
                offset=offset,
                from_date=from_date,
                to_date=to_date,
                status=status,
                supplier_id=supplier_id
            )
            purchases = await repo.get_purchase_by_shop_id(data=fetch_schema)

        # 3. Format Data
        headers = [
            "Purchase ID", "Invoice No", "Supplier ID",
            "Status", "Total Amount", "Tax Amount",
            "Items Count", "Purchase Date", "Created Date"
        ]

        rows = []
        for pur in (purchases or []):
            item_infos = pur.item_infos if isinstance(pur.item_infos, dict) else {}
            tax_infos = pur.gst_infos if isinstance(pur.gst_infos, dict) else {}
            
            tot_amt = item_infos.get("total_amount") or item_infos.get("total_order_amount") or 0.0
            tax_amt = tax_infos.get("total_tax", 0.0)
            items_count = len(pur.items) if getattr(pur, "items", None) else 0

            rows.append([
                pur.ui_id or pur.id,
                pur.invoice_no or "",
                pur.supplier_id or "",
                pur.status or "",
                tot_amt,
                tax_amt,
                items_count,
                pur.date.strftime("%Y-%m-%d") if isinstance(pur.date, datetime) else str(pur.date or ""),
                pur.created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(pur.created_at, datetime) else str(pur.created_at or "")
            ])

        # 4. Generate File Bytes
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "xlsx":
            file_bytes = generate_xlsx_bytes(headers, rows, sheet_name="Purchases")
            file_name = f"purchases_{shop_id}_{from_record}_{to_record}_{timestamp}.xlsx"
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            file_bytes = generate_csv_bytes(headers, rows)
            file_name = f"purchases_{shop_id}_{from_record}_{to_record}_{timestamp}.csv"
            content_type = "text/csv"

        # 5. Upload File
        download_url = await upload_export_file(
            file_bytes=file_bytes,
            filename=file_name,
            content_type=content_type
        )

        # 6. Update Redis status to COMPLETED
        result_data = {
            "job_id": job_id,
            "entity": "PURCHASE",
            "status": "COMPLETED",
            "download_url": download_url,
            "file_name": file_name,
            "total_records": len(rows),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }

        if job_id:
            await redis_client.set(
                f"EXPORT_JOB:{job_id}",
                json.dumps(result_data),
                ex=86400
            )

        # 7. Emit Notification Event
        await emit_notification(
            title="Purchase Export Ready",
            message=f"Export of {len(rows)} purchase records ({from_record}-{to_record}) is ready for download.",
            type="info",
            user_id=user_id or shop_id,
            additional_metadata={
                "download_url": download_url,
                "file_name": file_name,
                "entity": "PURCHASE",
                "count": len(rows),
                "job_id": job_id
            }
        )

        return result_data

    except Exception as e:
        ic(f"Error executing purchase export task: {e}")
        err_data = {
            "job_id": job_id,
            "entity": "PURCHASE",
            "status": "FAILED",
            "error": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        if job_id:
            await redis_client.set(
                f"EXPORT_JOB:{job_id}",
                json.dumps(err_data),
                ex=86400
            )
        return err_data
    finally:
        await redis_client.aclose()
