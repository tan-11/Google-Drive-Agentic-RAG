import requests
import json
import os
from app.config import Settings


def embed_text(text: str, settings: Settings):

    response = requests.post(
    url="https://openrouter.ai/api/v1/embeddings",
    headers={
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    },
    data=json.dumps({
        "model": "nvidia/llama-nemotron-embed-vl-1b-v2:free",
        "input": [
        {
            "content": [
            {"type": "text", "text": text}
            #{"type": "image_url", "image_url": {"url": "https://live.staticflickr.com/3851/14825276609_098cac593d_b.jpg"}}
            ]
        }
        ],
        "encoding_format": "float"
    })
    )

    data = response.json()

    if "data" not in data:
        raise ValueError(f"Embedding API error: {data}")

    return response.json()["data"][0]["embedding"]
