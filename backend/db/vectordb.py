import chromadb
import uuid
import numpy as np


class VectorDB:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./db_files/chroma_db")

        #RAG Chunks Collection
        self.chunk_collection = self.client.get_or_create_collection(name="chunks",
                                                                metadata={"hnsw:space": "cosine"})
        
        #LTM Summaries Collection
        self.ltm_collection = self.client.get_or_create_collection(name="ltm_summaries",
                                                              metadata={"hnsw:space": "cosine"})
        
        self.collections = {"chunks": self.chunk_collection,
                            "ltm": self.ltm_collection,}


    def add_vector(self, collection_name, embedding, metadata, vector_id):
        if vector_id is None:
            vector_id = str(uuid.uuid4())

        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()

        col = self.collections[collection_name]
        col.add(embeddings=[embedding],
                            metadatas=[metadata],
                            ids=[vector_id])


    def search(self, collection_name, embedding, session_id, n=3):
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
            
        col = self.collections[collection_name]
        return col.query(query_embeddings=[embedding],
                                     where={"session_id": session_id},
                                     n_results=n)
    

    def delete_session_embeddings(self, collection_name, session_id: str):
        col = self.collections[collection_name]
        col.delete(where={"session_id": session_id})


vectordb = VectorDB()