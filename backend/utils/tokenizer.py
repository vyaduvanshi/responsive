# from transformers import AutoTokenizer

#Commenting this out because was not able to instantiate this inside docker as it requires HF token

# tokenizer = AutoTokenizer.from_pretrained("meta-llama/Meta-Llama-3-8B-Instruct")

# def estimate_tokens(text: str) -> int:
#     if not text:
#         return 0
#     return len(tokenizer.encode(text))


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)