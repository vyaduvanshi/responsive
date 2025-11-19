from functools import lru_cache
from pathlib import Path


@lru_cache
def load_prompt(name: str) -> str:
    """
    Loads a prompt from app/utils/{name}
    """
    utils_dir = Path(__file__).resolve().parent
    prompt_path = utils_dir / name
    return prompt_path.read_text()