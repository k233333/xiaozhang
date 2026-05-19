"""ChromaDB 向量召回（默认禁用）

config.memory.enable_vector = True 时才生效。
默认关闭以省内存。
"""
from __future__ import annotations

from pathlib import Path

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


_collection: object | None = None


def _enabled() -> bool:
    return bool(settings.memory.enable_vector)


def _ensure_loaded() -> object | None:
    global _collection
    if _collection is not None:
        return _collection
    if not _enabled():
        return None
    try:
        import chromadb  # noqa: PLC0415

        path = Path(settings.resolve_path(settings.paths.data_dir)) / "chroma"
        path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(path))
        _collection = client.get_or_create_collection("xiaozhang_skills")
        log.info("ChromaDB 集合就绪", path=str(path))
    except Exception as e:  # noqa: BLE001
        log.warning("ChromaDB 加载失败，向量召回禁用", err=str(e))
        return None
    return _collection


def add(skill_name: str, trigger_text: str, metadata: dict | None = None) -> None:
    coll = _ensure_loaded()
    if coll is None:
        return
    coll.add(  # type: ignore[attr-defined]
        ids=[skill_name],
        documents=[trigger_text],
        metadatas=[metadata or {}],
    )


def query(text: str, n: int = 3) -> list[dict]:
    coll = _ensure_loaded()
    if coll is None:
        return []
    res = coll.query(query_texts=[text], n_results=n)  # type: ignore[attr-defined]
    out = []
    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    dists = res.get("distances", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    for i, name in enumerate(ids):
        out.append(
            {
                "skill_name": name,
                "document": docs[i] if i < len(docs) else "",
                "distance": dists[i] if i < len(dists) else None,
                "metadata": metas[i] if i < len(metas) else {},
            }
        )
    return out
