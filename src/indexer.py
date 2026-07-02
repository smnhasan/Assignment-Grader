import os
import json
import logging
import numpy as np
import faiss
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

# Ensure logs and data dirs exist before configuring logging
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/grader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BookIndexer:
    def __init__(self, book_path=None, save_dir="data/faiss_index"):
        load_dotenv("/home/nahid/Documents/Projects/finalsei/.env")
        self.book_path = book_path or "/home/nahid/Documents/Projects/finalsei/book/machine-learning-algorithms_text-book-partial.pdf"
        self.save_dir = save_dir
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.index = None
        self.chunks = []

    def get_embedding(self, text):
        """Helper to get embedding for a text string."""
        response = self.openai_client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        return response.data[0].embedding

    def get_embeddings_batch(self, texts):
        """Helper to get embeddings for a batch of text strings."""
        response = self.openai_client.embeddings.create(
            input=texts,
            model=self.embedding_model
        )
        return [item.embedding for item in response.data]

    def extract_text(self):
        """Extracts text page-by-page from the book PDF."""
        logger.info(f"Extracting text from {self.book_path}...")
        if not os.path.exists(self.book_path):
            raise FileNotFoundError(f"Book PDF not found at {self.book_path}")
        
        reader = PdfReader(self.book_path)
        pages_data = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_data.append({
                "text": text,
                "page": idx + 1  # 1-indexed page number
            })
        logger.info(f"Extracted {len(pages_data)} pages from book.")
        return pages_data

    def chunk_pages(self, pages_data, chunk_size=800, overlap=150):
        """Chunks page text into overlapping segments, preserving page metadata."""
        logger.info(f"Chunking book pages (size={chunk_size}, overlap={overlap})...")
        chunks = []
        for page_info in pages_data:
            text = page_info["text"]
            page_num = page_info["page"]
            
            # If the page is empty, skip it
            if not text.strip():
                continue
                
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "text": chunk_text,
                        "page": page_num
                    })
                start += (chunk_size - overlap)
        logger.info(f"Created {len(chunks)} chunks from the book.")
        return chunks

    def build_and_save_index(self, chunk_size=800, overlap=150):
        """Extracts text, chunks it, generates embeddings, and saves FAISS index to disk."""
        pages_data = self.extract_text()
        self.chunks = self.chunk_pages(pages_data, chunk_size, overlap)
        
        logger.info("Generating embeddings for all book chunks...")
        texts_to_embed = [chunk["text"] for chunk in self.chunks]
        
        # Embed in batches to avoid size limits or timeout
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts_to_embed), batch_size):
            batch = texts_to_embed[i:i + batch_size]
            logger.info(f"Embedding batch {i//batch_size + 1}/{-(-len(texts_to_embed)//batch_size)}...")
            embeddings = self.get_embeddings_batch(batch)
            all_embeddings.extend(embeddings)
            
        embeddings_arr = np.array(all_embeddings).astype('float32')
        
        # Normalize vectors for Cosine Similarity (Inner Product of normalized vectors)
        faiss.normalize_L2(embeddings_arr)
        
        # Create FAISS index
        dimension = embeddings_arr.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings_arr)
        
        # Save to disk
        os.makedirs(self.save_dir, exist_ok=True)
        faiss.write_index(self.index, os.path.join(self.save_dir, "index.faiss"))
        with open(os.path.join(self.save_dir, "chunks.json"), "w") as f:
            json.dump(self.chunks, f, indent=2)
            
        logger.info(f"FAISS index and chunks metadata successfully saved to {self.save_dir}.")

    def load_index(self):
        """Loads index and chunks metadata from disk. Returns True if successful, False otherwise."""
        index_path = os.path.join(self.save_dir, "index.faiss")
        chunks_path = os.path.join(self.save_dir, "chunks.json")
        
        if os.path.exists(index_path) and os.path.exists(chunks_path):
            logger.info(f"Loading FAISS index and chunks from {self.save_dir}...")
            self.index = faiss.read_index(index_path)
            with open(chunks_path, "r") as f:
                self.chunks = json.load(f)
            logger.info(f"Loaded FAISS index with {self.index.ntotal} elements.")
            return True
        else:
            logger.info("No existing FAISS index found on disk.")
            return False

    def get_or_create_index(self):
        """Loads index if it exists, otherwise builds it."""
        if not self.load_index():
            self.build_and_save_index()

    def search(self, query, k=5):
        """Performs cosine-similarity semantic search on the book chunks."""
        if self.index is None:
            self.get_or_create_index()
            
        query_embedding = self.get_embedding(query)
        query_vector = np.array([query_embedding]).astype('float32')
        faiss.normalize_L2(query_vector)
        
        distances, indices = self.index.search(query_vector, k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(self.chunks) and idx >= 0:
                results.append({
                    "text": self.chunks[idx]["text"],
                    "page": self.chunks[idx]["page"],
                    "score": float(dist)
                })
        return results

if __name__ == "__main__":
    # Test indexer
    indexer = BookIndexer()
    indexer.get_or_create_index()
    
    # Test search
    test_query = "What is regularized linear regression and Lasso?"
    logger.info(f"Testing search for: '{test_query}'")
    results = indexer.search(test_query, k=3)
    for idx, res in enumerate(results):
        print(f"\nResult {idx+1} (Page {res['page']}, Score: {res['score']:.4f}):")
        print(res["text"][:300])
