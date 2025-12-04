import os
import json
import pdfplumber
import numpy as np
import faiss
from datetime import datetime
from sentence_transformers import SentenceTransformer

from config_loaderapp import load_config



LOG_FILE = "pipeline_log.txt"

def write_log(message):
    """Append message to log file with timestamp."""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {message}\n")



def validate_pdf_path(pdf_path):
    """Ensure PDF exists and is valid."""
    if not os.path.isfile(pdf_path):
        write_log(f"ERROR: PDF not found — {pdf_path}")
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if not pdf_path.lower().endswith(".pdf"):
        write_log("ERROR: Provided file is not a PDF.")
        raise ValueError("Provided file is not a PDF.")

    write_log(f"PDF validated: {pdf_path}")
    return True


def validate_non_empty(data, error_msg):
    """Ensure data is not empty or None."""
    if data is None:
        raise ValueError(error_msg)
    if isinstance(data, list) and len(data) == 0:
        raise ValueError(error_msg)
    if isinstance(data, np.ndarray) and data.size == 0:
        raise ValueError(error_msg)
    return True



def extract_text_from_pdf(pdf_path):
    """Extract text from each PDF page."""
    write_log(f"Extracting text from PDF: {pdf_path}")
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
            else:
                write_log(f"WARNING: Empty or unreadable page {i+1}")

    validate_non_empty(pages, "PDF extraction failed — no text found.")
    write_log(f"Extracted text from {len(pages)} pages.")
    return pages



def recursive_chunk(text, separators, max_len):
    """Recursively split text into chunks under max_len."""
    text = text.strip()
    if len(text) <= max_len or not separators:
        return [text]

    sep = separators[0]
    parts = text.split(sep)

    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        if len(part) > max_len:
            chunks.extend(recursive_chunk(part, separators[1:], max_len))
        else:
            chunks.append(part)

    return chunks


def chunk_text(pages, max_len=400, separators=None):
    """Chunk entire PDF into list of text chunks."""
    write_log("Starting recursive chunking...")

    if separators is None:
        separators = ["\n\n", "."]

    all_chunks = []
    for text in pages:
        page_chunks = recursive_chunk(text, separators, max_len)
        for c in page_chunks:
            if c.strip():
                all_chunks.append(c)

    validate_non_empty(all_chunks, "Chunking failed — no chunks created.")
    write_log(f"Total chunks created: {len(all_chunks)}")
    return all_chunks



def generate_embeddings(chunks, model_name):
    """Generate embeddings using a SentenceTransformer model."""
    write_log(f"Generating embeddings using model: {model_name}")

    model = SentenceTransformer(model_name)
    embeddings = model.encode(chunks, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")  # FAISS requirement

    validate_non_empty(embeddings, "Embedding generation failed.")
    write_log(f"Generated {len(embeddings)} embeddings.")

    return embeddings, model



def build_faiss_index(embeddings, index_path):
    """Build a FAISS L2 index and save it."""
    write_log("Building FAISS IndexFlatL2...")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    if index.ntotal == 0:
        write_log("ERROR: FAISS index is empty.")
        raise ValueError("FAISS index is empty.")

    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    faiss.write_index(index, index_path)

    write_log(f"FAISS index saved at: {index_path}")
    return index


 

def save_chunks(chunks, json_path):
    """Save chunks to JSON file."""
    os.makedirs(os.path.dirname(json_path), exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=4, ensure_ascii=False)

    write_log(f"Chunks saved to: {json_path}")



def search_with_faiss(query, config):
    """Search chunks using FAISS index."""
    write_log(f"Searching for query: {query}")

    
    index = faiss.read_index(config["faiss_index_path"])

    
    with open(config["chunks_json"], "r", encoding="utf-8") as f:
        chunks = json.load(f)

    
    model = SentenceTransformer(config["embedding_model"])
    q_vec = model.encode([query], convert_to_numpy=True).astype("float32")

    
    k = config["top_k"]
    distances, ids = index.search(q_vec, k)

    results = []
    for rank, cid in enumerate(ids[0]):
        if cid < len(chunks):
            results.append({
                "rank": rank + 1,
                "chunk_id": int(cid),
                "distance": float(distances[0][rank]),
                "text": chunks[cid]
            })

    
    result_file = os.path.join(config["output_dir"], "retrieved.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    write_log(f"Search results saved to: {result_file}")
    return results




def run_pipeline():
    """Complete RAG pipeline."""
    config = load_config()

    write_log("===== Pipeline Started =====")

    
    pdf_files = [f for f in os.listdir(config["input_dir"]) if f.endswith(".pdf")]
    if not pdf_files:
        print("No PDF found in input directory.")
        return

    pdf_path = os.path.join(config["input_dir"], pdf_files[0])
    print("Processing PDF:", pdf_files[0])
    write_log(f"Processing PDF: {pdf_files[0]}")

    validate_pdf_path(pdf_path)

    
    pages = extract_text_from_pdf(pdf_path)

    
    chunks = chunk_text(pages, max_len=config["chunk_size"])
    save_chunks(chunks, config["chunks_json"])

    
    embeddings, _ = generate_embeddings(chunks, config["embedding_model"])

    
    build_faiss_index(embeddings, config["faiss_index_path"])

    print("\nPipeline Completed. Ready for search.\n")

    
    query = input("Enter your question: ").strip()
    if query:
        results = search_with_faiss(query, config)

        print("\nTop Retrieved Chunks:\n")
        for r in results:
            print(f"[{r['rank']}] Chunk {r['chunk_id']}  (Distance: {r['distance']:.4f})")
            print(r["text"][:300], "...\n")



if __name__ == "__main__":
    run_pipeline()
    