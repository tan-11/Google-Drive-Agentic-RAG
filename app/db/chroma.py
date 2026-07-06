import chromadb

class Chroma:
    def __init__(self, path: str = "data/chroma_data"):
        #self.client = chromadb.Client()
        # persistant data storage
        self.client = chromadb.PersistentClient(path=path) 

        self.collection = self.client.get_or_create_collection("all-my-documents")

    def add(self, documents: list[str], embeddings: list[list], metadatas : list[dict], ids: list[str]):
        self.collection.add(
            ids = ids,
            documents= documents,
            embeddings = embeddings,
            metadatas = metadatas
        )
 
    def retrieve_similar_documents(self, query_embeddings: list[list], n_results : int = 10):
        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )
        return results
