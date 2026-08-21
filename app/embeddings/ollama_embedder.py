import os

from ollama import Client


def _ollama_host():
    return os.getenv("OLLAMA_BASE_URL") or os.getenv(
        "OLLAMA_HOST",
        "http://localhost:11434",
    )


def _embedding_model():
    return os.getenv("OLLAMA_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "bge-m3")


class OllamaEmbedder:
    def __init__(self, model: str | None = None, host: str | None = None):
        self.model = model or _embedding_model()
        self.host = host or _ollama_host()
        self._client: Client | None = None

    @property
    def client(self):
        if self._client is None:
            self._client = Client(host=self.host)
        return self._client

    def embed(self, text: str) -> list[float]:
        response = self.client.embeddings(model=self.model, prompt=text)
        return response["embedding"]


ollama_embedder = OllamaEmbedder()
