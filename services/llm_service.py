import httpx
import json
from sentence_transformers import SentenceTransformer

from utils.prompt_utils import load_prompt



class LLMService:

    def __init__(self):
        self.embedding_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        self.llm_model = 'llama3.1:8b'
        self.http_client = httpx.AsyncClient(timeout=120.0)
    
    async def embed(self, text: str):
        vector = self.embedding_model.encode(text, show_progress_bar=False)
        return vector.astype("float32")
    

    async def generate_session_title(self, text: str) -> str:
        
        template = load_prompt("title_prompt.txt")
        title_prompt = template.format(text=text)
        raw_title = await self.chat(title_prompt)
        title = raw_title.strip()
        title = title.replace('"', "").replace("Title:", "").strip()

        #Fallback name
        if len(title) == 0:
            title = "Untitled Document"
        return title

    
    #Stream LLM response token by token
    async def chat_stream(self, prompt: str):
        async with self.http_client.stream("POST", "http://localhost:11434/api/generate",
                                           json={"model": self.llm_model, "prompt": prompt, "stream": True}) as response:
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "response" in data:
                            yield data["response"]  #yield each token
                    except json.JSONDecodeError:
                        continue

    #Non-streaming response (for summarization)
    async def chat(self, prompt: str):
        response = await self.http_client.post("http://localhost:11434/api/generate",
                                               json={"model": self.llm_model, "prompt": prompt, "stream": False})
        return response.json()["response"]
    

    async def summarize(self, prompt: str):
        return await self.chat(prompt)


llm_service = LLMService()
