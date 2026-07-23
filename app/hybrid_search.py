## ====================keyword search========================
import bm25s 
from app.db.sqlite import DB
db_client = DB()

class BM25Retriever:
    def __init__(self):
        self.chunks_with_ids = db_client.get_all_chunks()
        self.chunk_texts = [chunk['chunk_text'] for chunk in self.chunks_with_ids]
        self.chunk_ids = [chunk['chunk_id'] for chunk in self.chunks_with_ids]

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
from app.db.chroma import Chroma
from app.config import Settings

def get_top_k_chunks(query, settings : Settings, k=50):
    query_embedding = embedding.embed_text(query, settings)
    chroma_client = Chroma()

    return chroma_client.retrieve_similar_documents(query_embedding, n_results=k)


#==========================hybrid search========================
from app.rag.reranking import Reranker

reranker = Reranker()

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
    # get all chunks text
    chunks = db_client.get_chunks_by_ids(chunk_ids=[chunk_id for chunk_id, _ in rrf_results])
   
    chunk_texts = [chunk['chunk_text'] for chunk in chunks]
    map_chunk_id_text = {
        chunk['chunk_text']: (chunk["chunk_id"],chunk['name'], chunk['drive_link'])
        for chunk in chunks
        } 
    
    #rerank
    print("Reranking...")
    reranked_results = reranker.rerank(query, chunk_texts)
    print("Done reranking!")
    result = []
    for text, _ in reranked_results[:k]:
        chunk_id, file_name, drive_link = map_chunk_id_text[text]
        result.append(
            {
             "chunk_id": chunk_id,
             "chunk_text": text, 
             "file_name": file_name, 
             "drive_link": drive_link}
            )
    
    return result

