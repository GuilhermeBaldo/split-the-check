from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import boto3
from openai import OpenAI
from config import settings
from pydantic import BaseModel, field_validator

# Initialize FastAPI app
app = FastAPI(title="Check Processing API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AWS Textract client
textract = boto3.client(
    "textract",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


@app.post("/process-check/")
async def process_check(file: UploadFile = File(...)):
    """
    Process a check image to extract line items with their names and costs.
    """
    # Check if the file is an image
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        # Read the image file
        contents = await file.read()

        # Process with Amazon Textract
        response = textract.detect_document_text(Document={"Bytes": contents})

        # Extract text from Textract response
        extracted_text = ""
        for item in response["Blocks"]:
            if item["BlockType"] == "LINE":
                extracted_text += item["Text"] + "\n"

        # Use LLM to analyze the extracted text
        check = await extract_check_info(extracted_text)

        return {
            "status": "success",
            "check": check,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class LineItem(BaseModel):
    item: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    total_price: float | None = None

    @field_validator("quantity")
    def validate_quantity(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v

    @field_validator("unit_price", "total_price")
    def validate_prices(cls, v):
        if v is not None and v < 0:
            raise ValueError("Prices cannot be negative")
        return v

    @field_validator("total_price")
    def validate_total(cls, v, info):
        if v is not None:
            quantity = info.data.get("quantity")
            unit_price = info.data.get("unit_price")
            if quantity is not None and unit_price is not None:
                expected_total = quantity * unit_price
                if (
                    abs(v - expected_total) > 0.01
                ):  # Allow for small rounding differences
                    raise ValueError("Total price does not match quantity * unit price")
        return v


class ServiceFee(BaseModel):
    percent: float | None = None
    amount: float | None = None

    @field_validator("percent")
    def validate_percent(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Percentage must be between 0 and 100")
        return v

    @field_validator("amount")
    def validate_amount(cls, v):
        if v is not None and v < 0:
            raise ValueError("Amount cannot be negative")
        return v


class Check(BaseModel):
    line_items: list[LineItem] | None = None
    service_fee: ServiceFee | None = None
    subtotal: float | None = None
    total: float | None = None

    @field_validator("subtotal")
    def validate_subtotal(cls, v, info):
        if v is not None:
            if v < 0:
                raise ValueError("Subtotal cannot be negative")

            line_items = info.data.get("line_items")
            if line_items:
                items_total = sum(item.total_price or 0 for item in line_items)
                if abs(v - items_total) > 0.01:  # Allow for small rounding differences
                    raise ValueError("Subtotal does not match sum of line items")
        return v

    @field_validator("total")
    def validate_check_total(cls, v, info):
        if v is not None:
            if v < 0:
                raise ValueError("Check total cannot be negative")

            subtotal = info.data.get("subtotal")
            service_fee = info.data.get("service_fee")
            service_fee_amount = service_fee.amount if service_fee else 0

            if subtotal is not None:
                expected_total = subtotal + (service_fee_amount or 0)
                if (
                    abs(v - expected_total) > 0.01
                ):  # Allow for small rounding differences
                    raise ValueError(
                        "Check total does not match subtotal plus service fee"
                    )
            else:
                # Fallback to previous validation if subtotal is not provided
                line_items = info.data.get("line_items")
                if line_items:
                    items_total = sum(item.total_price or 0 for item in line_items)
                    expected_total = items_total + (service_fee_amount or 0)
                    if abs(v - expected_total) > 0.01:
                        raise ValueError(
                            "Check total does not match sum of line items and service fee"
                        )
        return v


async def extract_check_info(text: str) -> Check:
    """
    Use OpenAI's LLM to parse the OCR text and extract line items.
    """
    prompt = """
    Extract the line items from the following check receipt text. 
    For each item, identify the item name and its cost.
    Return the result as a JSON array of objects with 'item' and 'cost' properties.
    Format costs as floating point numbers.
    """

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.beta.chat.completions.parse(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        temperature=0,
        response_format=Check,
    )

    check = response.choices[0].message.parsed

    # Apply post-processing to convert item names to title case
    if check.line_items:
        for item in check.line_items:
            if item.item:
                item.item = item.item.title()

    return check


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
