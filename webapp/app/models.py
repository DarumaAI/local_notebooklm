from typing import List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    original_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    pages: Mapped[List["Page"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Page.page_number"
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    image_path: Mapped[str] = mapped_column(String)

    document: Mapped["Document"] = relationship(back_populates="pages")
    elements: Mapped[List["Element"]] = relationship(
        back_populates="page", cascade="all, delete-orphan", order_by="Element.element_index"
    )


class Element(Base):
    __tablename__ = "elements"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("pages.id"))
    element_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    classification: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    x0: Mapped[float] = mapped_column(Float)
    y0: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)

    page: Mapped["Page"] = relationship(back_populates="elements")
