from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.repositories import delete_product as delete_product_record
from app.repositories import save_product
from app.schemas import Product, ProductCreate
from app.state import app_state

router = APIRouter()


@router.get("", response_model=list[Product])
async def list_products() -> list[Product]:
    return list(app_state.products.values())


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str) -> Product:
    product = app_state.products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@router.post("", response_model=Product)
async def create_product(payload: ProductCreate) -> Product:
    product = Product(id=app_state.new_id("prod"), **payload.model_dump())
    app_state.products[product.id] = product
    save_product(product)
    return product


@router.put("/{product_id}", response_model=Product)
async def update_product(product_id: str, payload: ProductCreate) -> Product:
    if product_id not in app_state.products:
        raise HTTPException(status_code=404, detail="商品不存在")
    product = Product(id=product_id, **payload.model_dump())
    app_state.products[product_id] = product
    save_product(product)
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: str) -> dict[str, str]:
    if product_id not in app_state.products:
        raise HTTPException(status_code=404, detail="商品不存在")
    app_state.products.pop(product_id)
    delete_product_record(product_id)
    return {"status": "deleted", "deleted_at": datetime.utcnow().isoformat()}

