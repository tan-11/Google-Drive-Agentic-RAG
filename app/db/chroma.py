import chromadb

class Chroma:
    def __init__(self, path: str = "data/chroma_data"):
        #self.client = chromadb.Client()
        # persistant data storage
        self.client = chromadb.PersistentClient(path=path) 

        self.collection = self.client.get_or_create_collection("all-my-documents")

    def upsert(self, documents: list[str], embeddings: list[list], metadatas : list[dict], ids: list[str]):
        self.collection.upsert(
            ids = ids,
            documents = documents,
            embeddings = embeddings,
            metadatas = metadatas
        )
 
    def retrieve_similar_documents(self, query_embeddings: list[list], n_results : int = 10):
        results = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )
        return results
    
    def delete_rows_by_fileid(self, file_id:str):
        return self.collection.delete(
            where={"file_id": {"$eq": file_id}}
        )

    #testing
    def get_all_rows(self):
        results = self.collection.get(limit=10, include=["documents", "metadatas", "embeddings"] )
        for idx in range(len(results['ids'])):
            print(idx, ": \n", 
                  results['embeddings'][idx], "\n", 
                  results['documents'][idx], "\n",
                  results['metadatas'][idx])
        rows_count = self.collection.count()
        print("Total rows: ", rows_count)

