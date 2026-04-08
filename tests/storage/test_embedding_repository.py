import pytest

from src.storage import models
from src.storage.repositories import EmbeddingRepository


class _FakeSession:
    def __init__(self) -> None:
        self.registered_model: models.EmbeddingModel | None = None
        self.added: list[object] = []

    def scalar(self, _query):  # noqa: ANN001
        return self.registered_model

    def add(self, obj):  # noqa: ANN001
        self.added.append(obj)
        if isinstance(obj, models.EmbeddingModel):
            self.registered_model = obj

    def flush(self) -> None:
        return None


def test_embedding_repository_registers_model_dimensions_on_first_write() -> None:
    session = _FakeSession()
    repo = EmbeddingRepository(session=session)  # type: ignore[arg-type]

    row = repo.create(
        owner_id=1,
        model="openai/text-embedding-3-small",
        vector=[0.1, 0.2, 0.3],
        text_hash="abc",
    )

    assert isinstance(session.added[0], models.EmbeddingModel)
    assert session.registered_model is not None
    assert session.registered_model.model == "openai/text-embedding-3-small"
    assert session.registered_model.dimensions == 3
    assert isinstance(row, models.Embedding)
    assert row.dimensions == 3


def test_embedding_repository_rejects_dimension_mismatch_for_existing_model() -> None:
    session = _FakeSession()
    session.registered_model = models.EmbeddingModel(
        model="openai/text-embedding-3-small", dimensions=1536
    )
    repo = EmbeddingRepository(session=session)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="expects 1536 dimensions"):
        repo.create(
            owner_id=1,
            model="openai/text-embedding-3-small",
            vector=[0.1, 0.2],
            text_hash="abc",
        )
