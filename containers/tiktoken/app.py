from fastapi import FastAPI
from pydantic import BaseModel
import tiktoken

app = FastAPI(title="tiktoken-http", version="0.1.0")


class EncodeRequest(BaseModel):
    text: str
    encoding: str | None = "o200k_base"


class EncodeResponse(BaseModel):
    tokens: list[int]


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.post("/encode", response_model=EncodeResponse)
def encode(req: EncodeRequest):
    enc = tiktoken.get_encoding(req.encoding or "o200k_base")
    tokens = enc.encode(req.text or "")
    return EncodeResponse(tokens=tokens)
