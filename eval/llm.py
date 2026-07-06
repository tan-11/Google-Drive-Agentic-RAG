from openai import OpenAI
from app.config import get_settings
import time
import json

settings = get_settings()
client = OpenAI(api_key=settings.agnes_api_key,
                base_url = "https://apihub.agnes-ai.com/v1")

def get_response(prompt: str):
    for attempt in range(3):
        try:

            response = client.chat.completions.create(
                model="agnes-2.0-flash",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)

    if not response:
        raise RuntimeError("No response received")

    if not response.choices:
        raise ValueError("No choices returned by model")

    content = response.choices[0].message.content

    if not content:
        raise ValueError("Empty response content")

    return json.loads(content)