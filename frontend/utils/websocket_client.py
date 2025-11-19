import asyncio
import websockets

async def stream_chat(session_id: str, message: str):
    uri = f"ws://localhost:8000/chat/ws/{session_id}"
    
    async with websockets.connect(uri) as ws:
        await ws.send(message)
        
        async for msg in ws:
            if msg == "[DONE]":
                break
            yield msg