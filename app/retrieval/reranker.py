import os


RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")

try:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    print("WARNING: transformers/torch not installed. Reranker disabled.")


class BGEReranker:
    def __init__(self, model_name=RERANKER_MODEL):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        if not RERANKER_AVAILABLE:
            print("Reranker skipped: transformers/torch not available.")
            return
        try:
            print(f"Loading BGE Reranker model: {self.model_name} ...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.eval()
            self._loaded = True
            print("BGE Reranker loaded successfully.")
        except Exception as e:
            print(f"ERROR loading BGE Reranker: {e}. Reranker will be disabled.")
            self._loaded = False

    def rerank(self, query, documents, top_k=5):
        if not self._loaded or not documents:
            return documents[:top_k]
        try:
            texts = [doc["content_chunk"] for doc in documents]
            pairs = [[query, text] for text in texts]
            with torch.no_grad():
                inputs = self.tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )
                scores = self.model(**inputs).logits.squeeze(-1).tolist()
            if isinstance(scores, float):
                scores = [scores]
            scored = []
            for doc, score in zip(documents, scores):
                d = dict(doc)
                d["rerank_score"] = score
                scored.append(d)
            scored.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored[:top_k]
        except Exception as e:
            print(f"Reranking error: {e}. Falling back to original order.")
            return documents[:top_k]


def rerank_documents(query, documents, top_k=8):
    top_docs = bge_reranker.rerank(query, documents, top_k=top_k)
    if top_docs and top_docs[0].get("rerank_score") is not None:
        best_score = top_docs[0]["rerank_score"]
        if best_score < 0:
            return []
        threshold = best_score * 0.3
        return [d for d in top_docs if d.get("rerank_score", 0) >= threshold]
    return top_docs


bge_reranker = BGEReranker()
