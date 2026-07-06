import chromadb

class Chroma:
    def __init__(self):
        #self.client = chromadb.Client()
        # persistant data storage
        self.client = chromadb.PersistentClient(path="eval/data/test_embedding") 
        self.collection = self.client.get_or_create_collection("testing_chunks")

    def add(self,  ids: list[str], embeddings: list[list]):
        self.collection.add(
            ids = ids,
            embeddings = embeddings
        )
    
    def retrieve_similar_documents(self, query_embeddings: list[list], n_results : int = 10):
        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )
        return results 
