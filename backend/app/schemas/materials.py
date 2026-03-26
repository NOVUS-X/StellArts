from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class BOMLineInput(BaseModel):
    quantity: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)


class MaterialEstimateRequest(BaseModel):
    bom_text: str | None = Field(
        default=None,
        description="Raw bill-of-materials text from a scope of work.",
    )
    line_items: list[BOMLineInput] | None = None
    zip_code: str | None = Field(
        default=None,
        min_length=5,
        max_length=10,
        description="US ZIP used for localized pricing when the provider supports it.",
    )

    @model_validator(mode="after")
    def require_some_lines(self) -> MaterialEstimateRequest:
        has_text = bool(self.bom_text and self.bom_text.strip())
        has_items = bool(self.line_items)
        if not has_text and not has_items:
            raise ValueError("Provide bom_text and/or line_items")
        return self


class MaterialLineEstimate(BaseModel):
    description: str
    quantity: float
    search_query: str
    matched_title: str | None = None
    sku: str | None = None
    unit_price: float | None = None
    line_total: float | None = None
    currency: str | None = None
    status: str


class MaterialEstimateResponse(BaseModel):
    lines: list[MaterialLineEstimate]
    total_estimated_cost: float
    currency: str
    merchant: str
