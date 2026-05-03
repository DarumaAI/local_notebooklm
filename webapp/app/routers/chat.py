import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import GOOGLE_API_KEY
from ..database import get_session
from ..models import Document, Page

router = APIRouter()

QA_SYSTEM = """You are a precise and helpful question-answering assistant. Your task is to answer the user's question based strictly on the provided context.

Read the context carefully. The context is made up of multiple paragraphs, each preceded by an ID tag in the format `<ID: n>`.

Follow these strict rules:
1. Only use the information provided in the context to answer the question. Do not use outside knowledge.
2. If the answer cannot be found in the provided context, politely state: "I cannot answer this based on the provided context." Do not guess or make up an answer.
3. Every claim or fact in your answer MUST be supported by a citation to the relevant paragraph.
4. Format your citations using brackets containing the ID number at the end of the relevant sentence, like this: <citations>1</citations> or <citations>3</citations>.
5. If a sentence is supported by adjacent paragraphs, include the boundary IDs, like this: <citations>1-3</citations>.
6. If a sentence is supported by multiple paragraphs, include all relevant IDs, like this: <citations>1-3, 5, 17</citations>.

Ensure your answer is clear, concise, and accurate.
"""


class HistoryEntry(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[HistoryEntry]


class CitationOut(BaseModel):
    paragraph_id: int
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class ChatResponse(BaseModel):
    answer: str
    citations: List[CitationOut]


def _build_context(doc_id: int, session: Session):
    pages = (
        session.query(Page)
        .filter_by(document_id=doc_id)
        .order_by(Page.page_number)
        .all()
    )
    markdown = ""
    citations_map: dict[int, CitationOut] = {}
    pointer = 1
    for page in pages:
        for el in page.elements:
            markdown += f"<ID: {pointer}> {el.text}\n\n"
            citations_map[pointer] = CitationOut(
                paragraph_id=pointer,
                page=page.page_number,
                x0=el.x0,
                y0=el.y0,
                x1=el.x1,
                y1=el.y1,
            )
            pointer += 1
    return markdown, citations_map


def _parse_citations(answer: str, citations_map: dict) -> List[CitationOut]:
    pattern = r"<citations>(.*?)</citations>"
    seen: set[int] = set()
    result: List[CitationOut] = []
    for match in re.finditer(pattern, answer, re.DOTALL):
        for part in match.group(1).split(","):
            part = part.strip()
            if "-" in part:
                try:
                    a, b = part.split("-", 1)
                    ids: list[int] = list(range(int(a), int(b) + 1))
                except ValueError:
                    continue
            else:
                try:
                    ids = [int(part)]
                except ValueError:
                    continue
            for id_ in ids:
                if id_ in citations_map and id_ not in seen:
                    seen.add(id_)
                    result.append(citations_map[id_])
    return result


@router.post("/{doc_id}/chat", response_model=ChatResponse)
def chat(
    doc_id: int,
    req: ChatRequest,
    session: Session = Depends(get_session),
):
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not GOOGLE_API_KEY:
        raise HTTPException(
            status_code=503, detail="GOOGLE_API_KEY not configured"
        )

    context, citations_map = _build_context(doc_id, session)

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", api_key=GOOGLE_API_KEY
    )
    messages = [
        SystemMessage(content=QA_SYSTEM + "\n\n" + f"Context:\n{context}"),
    ]
    for entry in req.history:
        if entry.role == "user":
            messages.append(HumanMessage(content=entry.content))
        elif entry.role == "ai":
            messages.append(AIMessage(content=entry.content))
        else:
            raise NotImplementedError(
                f"Message role {entry.role} is not implemented."
            )
    messages.append(HumanMessage(content=req.question))
    response = model.invoke(messages)

    answer = response.content
    citations = _parse_citations(answer, citations_map)
    return ChatResponse(answer=answer, citations=citations)
