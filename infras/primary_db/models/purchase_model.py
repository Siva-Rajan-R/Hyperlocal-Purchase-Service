from ..main import BASE
from sqlalchemy import (
    Column, String, Float, Boolean, BigInteger,ARRAY,
    TIMESTAMP, func, ForeignKey, Identity
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB


class Purchase(BASE):
    __tablename__ = "purchase"

    id = Column(String, primary_key=True)
    sequence_id = Column(BigInteger, Identity(always=True), nullable=False)

    ui_id = Column(String, nullable=False, index=True)
    shop_id = Column(String, nullable=False)
    supplier_id = Column(String, nullable=False)
    invoice_no=Column(String)

    type = Column(String, nullable=False)
    purchase_view = Column(Boolean, nullable=False)

    calculation_infos = Column(JSONB, nullable=False)
    charges_infos = Column(JSONB, nullable=False)
    item_infos = Column(JSONB, nullable=False)

    payment_infos = Column(ARRAY(JSONB), nullable=False)

    date = Column(TIMESTAMP(), nullable=False)

    additional_infos = Column(JSONB)

    created_at = Column(TIMESTAMP(timezone=True),nullable=False,server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    items = relationship(
        "PurchaseItems",
        back_populates="purchase",
        cascade="all, delete-orphan"
    )


class PurchaseItems(BASE):
    __tablename__ = "purchase_items"

    id = Column(String, primary_key=True)

    purchase_id = Column(
        String,
        ForeignKey("purchase.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    product_id = Column(String, nullable=False)
    variant_id = Column(String)
    batch_id = Column(String)
    serialno_id = Column(String)
    serial_numbers=Column(ARRAY(String))

    gst = Column(String)

    stocks = Column(Float, nullable=False)
    stocks_before = Column(Float, nullable=False)
    stocks_after=Column(Float, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    purchase = relationship(
        "Purchase",
        back_populates="items"
    )

    pricing_infos = relationship(
        "PurchaseItemsPricing",
        back_populates="purchase_item",
        cascade="all, delete-orphan"
    )

    storage_locations = relationship(
        "PurchaseItemsStoragelocation",
        back_populates="purchase_item",
        cascade="all, delete-orphan"
    )

    reorder_point = relationship(
        "PurchaseItemsReorderPoint",
        back_populates="purchase_item",
        cascade="all, delete-orphan"
    )


class PurchaseItemsPricing(BASE):
    __tablename__ = "purchase_items_pricing"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    pricing_id = Column(String, nullable=False)

    purchase_id = Column(
        String,
        ForeignKey("purchase.id", ondelete="CASCADE"),
        nullable=False
    )

    purchase_item_id = Column(
        String,
        ForeignKey("purchase_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    buy_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    purchase_item = relationship(
        "PurchaseItems",
        back_populates="pricing_infos"
    )



class PurchaseItemsReorderPoint(BASE):
    __tablename__ = "purchase_items_reorder_point"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    reorder_point_id = Column(String, nullable=False)

    purchase_id = Column(
        String,
        ForeignKey("purchase.id", ondelete="CASCADE"),
        nullable=False
    )

    purchase_item_id = Column(
        String,
        ForeignKey("purchase_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    reorder_point=Column(Float,nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    purchase_item = relationship(
        "PurchaseItems",
        back_populates="reorder_point"
    )


class PurchaseItemsStoragelocation(BASE):
    __tablename__ = "purchase_items_storagelocation"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    storage_location_id = Column(String, nullable=False)

    purchase_id = Column(
        String,
        ForeignKey("purchase.id", ondelete="CASCADE"),
        nullable=False
    )

    purchase_item_id = Column(
        String,
        ForeignKey("purchase_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name = Column(String, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    purchase_item = relationship(
        "PurchaseItems",
        back_populates="storage_locations"
    )