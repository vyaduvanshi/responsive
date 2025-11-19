# responsive

### Document RAG Chatbot

#### Instructions to run:

1. Git clone repo to your local
2. Navigate to the project root directory, and launch the terminal
3. Run this command ```docker compose up --build```
4. Wait for all libraries, models, etc to download. Might take a few minutes.
5. Once the image is built and the container is running, wait for Ollama to finish pulling.
6. Once it's ready, feel free to access the following URLs-
    i. Streamlit UI → http://localhost:8501
    ii. FastAPI backend → http://localhost:8000

<br>

![AAS](assets/rag-chatbot-system-design.png)

<br>

## Memory Management Explanation

$Prompt = Query + Retrieved Context + ShortTermMemory (STM) + Retrieved LongTermMemory (LTM)$

**1. User sends a query**
* Add message to STM (Redis + SQLite)
* Possibly trigger summarization

**2. When STM > Threshold**
* Fetch STM and summarize it
* Store this summarization into LTM
* Delete STM rows
* Clear Redis STM cache
* Embed LTM summary → store in ChromaDB

**3. Retrieval workflow**
* On every query:
    * Get STM messages
    * Embed user query
    * Retrieve top-k document chunks
    * Recall relevant LTM summary from ChromaDB
    * Construct full RAG prompt
    * Send to LLM streaming

**4. Store assistant response**
* Add to STM
* Add to chat history (persistent)

**5. Delete session**
* Delete STM from Redis
* In background task:
    * Delete STM/LTM from SQLite
    * Delete chat history
    * Delete chunks + document
    * Delete embeddings from ChromaDB
    * Delete session row

**6. Switch session**
* Clear STM memory from Redis
* Load STM memory of new session from SQLite to Redis



<br>




#### Memory Storage Locations
| Component         | Storage            | What it is |
| ----------------- | ------------------ |--------|
| Session          | SQLite             |Keeps track of sessions/chats|
| Document          | SQLite             |Stores uploaded document metadata|
| DocumentChunks    | SQLite             |Stores document chunks|
| ChunkEmbeddings   | ChromaDB           |Stores vectorised embeddings of chunks|
| ShortTermMemory   | Redis              | Stores short term memory for super quick access|
| LongTermMemory    | SQLite             | Stores summaries of STM when they cross a threshold        |
| SessionChatHistory        | SQLite | Stores entire chat history for loading back when user resumes session        |
| LTM Embeddings | ChromaDB | Stores vectorised embeddings of long term memories |



<br>

#### Further Possible Improvements

* Increase latency by by lowering precision from float32  to float16 
* Add LRU cache python decorator for chunk embeddings, in case of same document uploaded twice.
* Parallelise processes such as chunk embedding
* Replace SQLite with Postgres for high-scale use
* Fingerprinting for chunk_id
* Hybrid search (keyword + vector)
* UI features such as user login, PDF preview in UI, multi-files ingestion, etc.