from openai import OpenAI
from app.config import get_settings
from app.db.sqlite import DB
from app.domain import Conversation

db_client = DB()


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.agnes_api_key,
                             base_url = "https://apihub.agnes-ai.com/v1")

    def conversation_naming(self, first_conversation: str) -> str:
        system_msg = [{"role": "system", "content": "You are a conversation summary naming assistant."}]
        prompt = f"""
Your task is to generate a concise and descriptive name for the following conversation. 

## Instruction
The name should be clear, relevant, and capture the essence of the conversation. 
Focus on the main topic or theme discussed in the conversation.
Restrict the maximum name length in 5 words. 3-5 will be good.

## Conversation:
{first_conversation}

**Output in only the name**.

"""
        messages = [
            {"role": "user", "content": prompt},
        ]

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model="agnes-2.0-flash",
                    messages=system_msg + messages,
                )
                break
            except Exception as e:
                print(f"{attempt+1} tries failed : {e}")
                
        return response.choices[0].message.content.strip()