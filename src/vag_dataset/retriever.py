from typing import List

from models import Coordinates, Element, Page
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

_COLLECTION = "documents"
_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


class DocumentRetriever:
    def __init__(
        self, pages: List[Page], db_path: str = "./milvus_lite.db"
    ) -> None:
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._client = MilvusClient(db_path)

        if self._client.has_collection(_COLLECTION):
            self._client.drop_collection(_COLLECTION)

        self._client.create_collection(
            collection_name=_COLLECTION,
            dimension=_EMBEDDING_DIM,
            enable_dynamic_field=True,
        )

        records = []
        for idx, (page, el) in enumerate(
            (page, el) for page in pages for el in page.content
        ):
            records.append(
                {
                    "id": idx,
                    "vector": self._model.encode(el.text).tolist(),
                    "text": el.text,
                    "page_number": page.number,
                    "element_id": el.id,
                    "classification": el.classification or "",
                    "x0": float(el.coordinates.x0),
                    "y0": float(el.coordinates.y0),
                    "x1": float(el.coordinates.x1),
                    "y1": float(el.coordinates.y1),
                }
            )

        if records:
            self._client.insert(collection_name=_COLLECTION, data=records)

    def retrieve(self, query: str, top_k: int = 5) -> List[Element]:
        query_vec = self._model.encode(query).tolist()
        results = self._client.search(
            collection_name=_COLLECTION,
            data=[query_vec],
            limit=top_k,
            output_fields=[
                "text",
                "element_id",
                "classification",
                "x0",
                "y0",
                "x1",
                "y1",
            ],
        )

        elements = []
        for hit in results[0]:
            e = hit["entity"]
            elements.append(
                Element(
                    text=e["text"],
                    id=e["element_id"],
                    classification=e["classification"] or None,
                    coordinates=Coordinates(
                        x0=e["x0"],
                        y0=e["y0"],
                        x1=e["x1"],
                        y1=e["y1"],
                    ),
                )
            )

        return elements
