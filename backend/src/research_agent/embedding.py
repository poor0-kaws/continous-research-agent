from collections.abc import Iterable

from fastembed import TextEmbedding


class LocalEmbedder:
    def __init__(self) -> None:
        self._model: TextEmbedding | None = None

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        if self._model is None:
            self._model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        passages = [f"passage: {text}" for text in texts]
        return [vector.tolist() for vector in self._model.embed(passages)]
