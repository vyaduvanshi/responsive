from transformers import AutoTokenizer


tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(tokenizer.encode(text))