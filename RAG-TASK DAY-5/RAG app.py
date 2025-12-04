import json
import os
import pdfplumber
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from sentence_transformers.cross_encoder import CrossEncoder
from datetime import datetime
import sys

from config_loaderapp import load_config



def log_error(e, func_name, logfile):
    try:
        tb = sys.exc_info()[2]
        lineno = tb.tb_lineno if tb else "N/A"
        msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR in {func_name} line {lineno}: {e}"

        print(msg)
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except:
        print("Logging failed.")



def get_pdf_text(pdf_path, logfile):
    try:
        text_pages = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text_pages.append(page.extract_text() or "")
        return "\n".join(text_pages)
    except Exception as e:
        log_error(e, "get_pdf_text", logfile)
        return ""



def make_chunks(text, size):
    return [text[i:i + size].strip() for i in range(0, len(text), size)]



def embed_text(chunks, model_name):
    model = SentenceTransformer(model_name)
    return model.encode(chunks, convert_to_numpy=True)


def build_faiss_index(embeddings, index_path):
    dim = embeddings.shape[1]
   
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    os.makedirs(os.path.dirname(index_path), exist_ok=True)

    faiss.write_index(index, index_path)
    return index


def save_chunks(chunks, chunk_path):
    os.makedirs(os.path.dirname(chunk_path), exist_ok=True)
    with open(chunk_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=4, ensure_ascii=False)



def search_pdf(query, config):
    index = faiss.read_index(config["faiss_index_path"])

    with open(config["chunks_json"], "r", encoding="utf-8") as f:
        chunks = json.load(f)

    model = SentenceTransformer(config["embedding_model"])
    q_vec = model.encode([query], convert_to_numpy=True)
    faiss.normalize_L2(q_vec)

    top_k = config["top_k"]
    scores, ids = index.search(q_vec, top_k)

    candidate_ids = [i for i in ids[0] if i < len(chunks)]

    rerank_n = config["rerank_top_n"]
    reranker = CrossEncoder(config["reranker_model"])

    rerank_pairs = [(query, chunks[i]) for i in candidate_ids[:rerank_n]]
    rerank_scores = reranker.predict(rerank_pairs)

    results = []
    for i, cid in enumerate(candidate_ids[:rerank_n]):
        results.append({
            "text": chunks[cid],
            "score": float(rerank_scores[i])
        })

    results = sorted(results, key=lambda x: x["score"], reverse=True)
    return results



def run_pipeline():
    config = load_config()
    logfile = os.path.join(config["log_dir"], config["log_file"])

    pdf_files = [file for file in os.listdir(config["input_dir"]) if file.endswith(".pdf")]

    if not pdf_files:
        print("No PDF found in input folder.")
        return

    pdf_path = os.path.join(config["input_dir"], pdf_files[0])
    print("Processing PDF:", pdf_files[0])

    
    text = get_pdf_text(pdf_path, logfile)

    
    chunks = make_chunks(text, config["chunk_size"])
    save_chunks(chunks, config["chunks_json"])

    
    embeddings = embed_text(chunks, config["embedding_model"])

    
    build_faiss_index(embeddings, config["faiss_index_path"])

    print("\nPipeline finished. You can now search your PDF.\n")

    query = input("Enter your question: ").strip()

    if query:
        results = search_pdf(query, config)
        print("\nTop Answers:\n")
        for r in results:
            print(f"Score: {r['score']:.4f}\n{r['text'][:400]}...\n{'-'*50}")


if __name__ == "__main__":
    run_pipeline()
