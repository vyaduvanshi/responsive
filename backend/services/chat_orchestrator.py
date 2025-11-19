import logging
import numpy as np
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from db.vectordb import vectordb
from services.memory_service import memory_service
from services.llm_service import llm_service
from utils.prompt_utils import load_prompt
from utils.tokenizer import estimate_tokens


logger = logging.getLogger(__name__)



class ChatOrchestrator:

    def __init__(self, short_term_token_limit: int = 2000,
                 response_token_limit: int = 4000, k_retrieval: int = 3):
        """
        Parameters:

        short_term_token_limit: When to summarize short-term memory
        response_token_limit: Max tokens to send to LLM for final prompt
        k_retrieval: Top-k chunks retrieved
        """

        self.short_term_token_limit = short_term_token_limit
        self.response_token_limit = response_token_limit
        self.k = k_retrieval


    async def process_message(self, session_id: str, user_message: str, db: AsyncSession):
        
        logger.info(f"Session id: [{session_id}] Received message: {user_message}")

        #1. Appending user message to short term memory
        await memory_service.add_short_term(session_id=session_id, role="user", 
                                            content=user_message, db=db)
        logger.info(f"Appended user message to short term memory for session id: {session_id}")

        #2. Checking for summarization threshold of short term memory
        logger.info(f"Checking if STM > Threshold for summarization, for session id:{session_id}")
        await memory_service.maybe_summarize(session_id, db)

        #3. Fetching short term and long term memories
        short_memory = await memory_service.get_short_term(session_id, db)
        
        #Selective LTM recall
        ltm_embeddings = await llm_service.embed(user_message)
        res = vectordb.search(collection_name="ltm", embedding=ltm_embeddings, session_id=session_id, n=1)
        metas = res.get("metadatas", [[]])[0]
        if metas:
            long_memory = [metas[0]["summary"]]
        else:
            long_memory = []
        logger.info(f"[{session_id}] Loaded short term ({len(short_memory)} turns) and long term ({len(long_memory)}) memories")

        #4. Embedding user message (query) and retrieving top-k chunks
        query_emb = await llm_service.embed(user_message)
        if isinstance(query_emb, list):
            query_emb = np.array(query_emb, dtype="float32")
        logger.info(f"Obtained query embedding (dim={query_emb.shape}) for session id: {session_id}")

        #5. Running similarity search to retrieve similar embeddings
        results = vectordb.search(collection_name='chunks', embedding=query_emb, session_id=session_id, n=3)
        metadatas = results.get("metadatas", [[]])[0]
        doc_contexts = [md.get("text", "") for md in metadatas]
        logger.info(f"[{session_id}] Ran similarity search and retrieved {len(doc_contexts)} document chunks from ChromaDB")

        #6. Building final prompt
        prompt = self._build_prompt(user_message, short_memory, long_memory, doc_contexts)
        used_tokens = estimate_tokens(prompt)
        logger.info(f"[{session_id}] Built prompt (approx tokens={used_tokens})")

        if used_tokens > self.response_token_limit:
            logger.info(f"[{session_id}] Prompt exceeds token budget, trimming")
            prompt = self._trim_prompt(prompt, long_memory, doc_contexts, short_memory, user_message)
            logger.info(f"[{session_id}] Trimmed prompt (approx tokens={estimate_tokens(prompt)})")

        logger.info(f"FULL PROMPT:\n{prompt}")

        #7. Streaming LLM response
        logger.info(f"[{session_id}] Streaming prompt to LLM (streaming)")
        full_response = ""
        
        async for token in llm_service.chat_stream(prompt):
            full_response += token
            yield token  #stream to client
        
        logger.info(f"[{session_id}] LLM completed (len={len(full_response)} chars)")

        #8. Append complete assistant response to short-term memory
        await memory_service.add_short_term(session_id=session_id,
                                            role="assistant",
                                            content=full_response,
                                            db=db)
        logger.info(f"Appended assistant response to short-term memory for session id: {session_id}")

        

    def _build_prompt(self, user_message: str, short_memory: List[dict], long_memory: List[str], doc_contexts: List[str]) -> str:
        
        long_text = "\n".join([f"- {s}" for s in long_memory]) if long_memory else "No long-term memory."
        doc_text = "\n\n".join([f"CHUNK {i+1}:\n{c}" for i, c in enumerate(doc_contexts)]) if doc_contexts else "No document context found."
        short_text = "\n".join([f"{m['role']}: {m['content']}" for m in short_memory]) if short_memory else "No short-term memory."

        template = load_prompt("rag_prompt.txt")
        prompt = template.format(long_text=long_text, doc_text=doc_text, doc_count=len(doc_contexts),
                                 short_text=short_text, user_message=user_message)
        return prompt.strip()


    def _trim_prompt(self, prompt: str, long_memory: List[str],
                     doc_contexts: List[str], short_memory: List[dict], user_message: str) -> str:
        
        #Return as-is if under the limit
        budget = self.response_token_limit
        if estimate_tokens(prompt) <= budget:
            return prompt

        #Step 1: Shorten document chunks
        short_docs = []
        for c in doc_contexts:
            words = c.split()
            short_docs.append(" ".join(words[:80]) + (" ..." if len(words) > 80 else ""))
        prompt2 = self._build_prompt(user_message, short_memory, long_memory, short_docs)
        if estimate_tokens(prompt2) <= budget:
            return prompt2

        #Step 2: Keep only top-1 document chunk
        top1_docs = short_docs[:1]
        prompt3 = self._build_prompt(user_message, short_memory, long_memory, top1_docs)
        if estimate_tokens(prompt3) <= budget:
            return prompt3

        #Step 3: Keep only last 2 short-term messages
        last_short = short_memory[-2:] if len(short_memory) > 2 else short_memory
        prompt4 = self._build_prompt(user_message, last_short, long_memory, top1_docs)
        if estimate_tokens(prompt4) <= budget:
            return prompt4

        #Step 4: Trim user message
        user_words = user_message.split()
        half_user = " ".join(user_words[:150]) + "..."

        prompt5 = self._build_prompt(half_user, last_short, long_memory, top1_docs)
        return prompt5


# create singleton
chat_orchestrator = ChatOrchestrator()
