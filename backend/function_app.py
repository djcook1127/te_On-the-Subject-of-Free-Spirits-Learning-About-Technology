"""Azure FunctionsのHTTP入口。ローカルのuvicorn起動には影響しない。"""
import os

import azure.functions as func

os.environ["GIFTIA_ROOM_STORAGE"] = "shared"
os.environ["GIFTIA_CATALOG_SOURCE"] = "shared"
os.environ["GIFTIA_SECURE_COOKIES"] = "1"

from selection_rooms import app as fastapi_app
from product_catalog import read_only_cursor


@fastapi_app.get("/api/health")
def health():
    with read_only_cursor() as cursor:
        cursor.execute("SELECT 1 FROM products LIMIT 1")
        cursor.fetchone()
        cursor.execute("SELECT token_hash FROM consultation_invites LIMIT 1")
        cursor.fetchone()
    return {"db": "MySQL"}


app = func.AsgiFunctionApp(app=fastapi_app, http_auth_level=func.AuthLevel.ANONYMOUS)
