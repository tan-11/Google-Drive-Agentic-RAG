## ====================keyword search========================
import bm25s

from app.db.chroma import Chroma
from app.db.sqlite import DB
db_client = DB()

class BM25Retriever:
    def __init__(self):
        self.chunks_with_ids = db_client.get_all_chunks()
        valid_chunks = [
                    chunk
                    for chunk in self.chunks_with_ids
                    if chunk.get("chunk_text")
                    and chunk["chunk_text"].strip()
                ]

        self.chunk_texts = [
            chunk["chunk_text"]
            for chunk in valid_chunks
        ]


        self.chunk_ids = [chunk['chunk_id'] for chunk in valid_chunks]

        if not self.chunk_texts:
            raise ValueError("No valid chunks found for BM25 indexing")
        
        self.tokenized_corpus = bm25s.tokenize(self.chunk_texts)
        self.bm25_retriever = bm25s.BM25()
        self.bm25_retriever.index(self.tokenized_corpus)

    def retrieve(self, query: str, k: int = 50) -> tuple[list[str], list[float]]:
        query_tokens = bm25s.tokenize([query])
        results, scores = self.bm25_retriever.retrieve(query_tokens, k=k)
        return {"ids": self.map_results_to_chunks_ids(results[0]), "scores": scores.tolist()}
    
    def map_results_to_chunks_ids(self, results: list[int]) -> list[str]:
        return [self.chunk_ids[i] for i in results]
    

# ===========================semantic search========================
import app.rag.embedding as embedding
from app.config import Settings

def get_top_k_chunks(query, settings : Settings, k=50):
    query_embedding = embedding.embed_text(query, settings)
    chroma_client = Chroma()

    return chroma_client.retrieve_similar_documents(query_embedding, n_results=k)


#==========================hybrid search========================
from app.rag.reranking import Reranker

_reranker: Reranker | None = None


def _get_reranker() -> Reranker:
    global _reranker

    if _reranker is None:
        _reranker = Reranker()

    return _reranker

def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    
    ## reciprocal_rank_fusion
    ## Performs Reciprocal Rank Fusion on multiple ranked lists.
    
    rrf_scores = {}
    
    for ranked_list in rankings:
        # rank starts at 1 for the formula
        for rank, doc_id in enumerate(ranked_list, start=1):
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
            
            # Apply the standard RRF formula
            rrf_scores[doc_id] += 1.0 / (k + rank)
            
    # Sort documents by their calculated RRF score in descending order
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


def hybrid_search(query: str, settings : Settings, k:int =20):
    keyword_results = BM25Retriever().retrieve(query)
    semantic_results = get_top_k_chunks(query, settings=settings)
    #rrf ranking
    rrf_results = rrf([keyword_results['ids'], semantic_results['ids'][0]])
    chunk_ids = [chunk_id for chunk_id, _ in rrf_results]

    file_rows = db_client.get_chunks_by_ids(chunk_ids=chunk_ids)
    chroma_rows = Chroma().get_chunks_by_ids(chunk_ids=chunk_ids)

    file_by_id = {chunk["chunk_id"]: chunk for chunk in file_rows}
    metadata_by_id = {
        chunk["chunk_id"]: chunk.get("metadata", {})
        for chunk in chroma_rows
    }

    candidate_chunks = []
    for chunk_id in chunk_ids:
        file_row = file_by_id.get(chunk_id)
        if not file_row:
            continue

        chunk_text = file_row.get("chunk_text", "")
        if not chunk_text.strip():
            continue

        metadata = metadata_by_id.get(chunk_id, {})
        page_number = metadata.get("page_number")

        candidate_chunks.append(
            {
                "chunk_id": chunk_id,
                "chunk_text": chunk_text,
                "file_name": file_row["name"],
                "drive_link": file_row["drive_link"],
                "page_number": page_number,
                "section_heading": metadata.get("section_heading"),
                "sheet_name": metadata.get("sheet_name"),
            }
        )

    print("Reranking...")
    reranked_results = _get_reranker().rerank(query, candidate_chunks)
    print("Reranking done!")
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "chunk_text": chunk["chunk_text"],
            "file_name": chunk["file_name"],
            "drive_link": chunk["drive_link"],
            "page_number": chunk.get("page_number"),
            "section_heading": chunk.get("section_heading"),
            "sheet_name": chunk.get("sheet_name"),
        }
        for chunk in reranked_results[:k]
    ]
