import os
from dotenv import load_dotenv

# Try loading from local workspace root first, then fall back to the absolute path
local_env = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(local_env):
    load_dotenv(local_env)
else:
    load_dotenv("/home/nahid/Documents/Projects/finalsei/.env")

# API Keys and Models
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("MODEL", "gpt-5.4-nano")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# Default textbook path fallback
DEFAULT_BOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 
    "book", 
    "machine-learning-algorithms_text-book-partial.pdf"
)
if not os.path.exists(DEFAULT_BOOK_PATH):
    DEFAULT_BOOK_PATH = "/home/nahid/Documents/Projects/finalsei/book/machine-learning-algorithms_text-book-partial.pdf"
