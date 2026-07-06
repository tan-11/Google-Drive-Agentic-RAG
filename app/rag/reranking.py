import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from app.config import get_settings
import os

settings = get_settings()
os.environ["HF_TOKEN"] = settings.hf_token

class Reranker:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained('BAAI/bge-reranker-v2-m3')
        self.model = AutoModelForSequenceClassification.from_pretrained('BAAI/bge-reranker-v2-m3')
        self.model.eval()

    def rerank(self, query: str, candidate_chunks: list[str]) -> list[tuple[str, float]]:
        pairs = [[query, chunk] for chunk in candidate_chunks]

        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
            scores = self.model(**inputs, return_dict=True).logits.view(-1, ).float()
        
        return sorted(list(zip(candidate_chunks, scores.tolist())), reverse=True, key=lambda x: x[1])

