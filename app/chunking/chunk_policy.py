from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkPolicy:
    max_words: int = 450
    overlap: int = 60
    min_words: int = 20
    preserve_paragraphs: bool = True

    def normalized(self) -> "ChunkPolicy":
        max_words = max(1, int(self.max_words or 450))
        overlap = max(0, int(self.overlap or 0))
        if overlap >= max_words: 
            overlap = max(0, max_words // 5)
        min_words = max(1, min(int(self.min_words or 1), max_words))
        return ChunkPolicy(
            max_words=max_words,
            overlap=overlap,
            min_words=min_words,
            preserve_paragraphs=bool(self.preserve_paragraphs),
        )


DEFAULT_CHUNK_POLICY = ChunkPolicy()
