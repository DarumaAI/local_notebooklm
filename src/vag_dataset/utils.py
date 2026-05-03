import re
from typing import Dict, List, Tuple

from langchain.text_splitter import CharacterTextSplitter
from models import (
    AttributedAnswer,
    Citation,
    Coordinates,
    DocumentChunk,
    Element,
)


def convert_to_k(
    coords: Coordinates,
) -> Tuple[int, int, int, int]:
    """
    Converst coordinates to a list of integers if they are provided as float values between 0 and 1.
    """
    assert len(coords) == 4

    if not all(x >= 0 and x <= 1 for x in coords.__dict__.values()):
        return list(map(int, coords.__dict__.values()))

    return tuple([int(x * 1000) for x in coords.__dict__.values()])


def convert_to_markdown(
    input: List[Element],
) -> Tuple[str, Dict[int, Tuple[int, int]]]:
    assert len(set([x.document for x in input])) == 1

    input = sorted(input, key=lambda x: (x.page_n, x.id))

    markdown_doc = ""
    citations_map = dict()
    pointer = 1
    for el in input:
        markdown_doc += f"<ID: {pointer}> {el.text}\n\n"
        citations_map[pointer] = (el.page_n, el.id)

        pointer += 1

    return markdown_doc, citations_map


def map_to_boxes(
    answer: str,
    citations_map: Dict[int, Tuple[str, str]],
    doc: List[Element],
    placeholders: Tuple[str, str] = ("<citations>", "</citations>"),
) -> AttributedAnswer:
    """
    Transforms an answer into an attributed answer.

    **Args**
    answer: the answer with attributions delimited by <citations> </citations>.
    citations_map: the mapping of citation indexes to page-layout_index in order to identify the element in the document.
    doc: the list of pages.
    placeholders: the strings limiting the beginning and end of citations.
    """
    open_tag, close_tag = placeholders

    element_lookup = {(el.page_n, el.id): el for el in doc}

    citations = []
    pattern = re.escape(open_tag) + r"(.*?)" + re.escape(close_tag)

    for match in re.finditer(pattern, answer, re.DOTALL):
        start_idx, end_idx = match.start(), match.end()

        ids: List[int] = []
        for part in match.group(1).split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                ids.extend(range(int(a), int(b) + 1))
            else:
                ids.append(int(part))

        for id_ in ids:
            if id_ not in citations_map:
                continue
            page_n, el_id = citations_map[id_]
            el = element_lookup.get((page_n, el_id))
            if el is None:
                continue
            citations.append(
                Citation(
                    start_idx=start_idx,
                    end_idx=end_idx,
                    page=page_n,
                    bbox=el.coordinates,
                )
            )

    return AttributedAnswer(answer=answer, citations=citations)


# TODO: test this function
def chunk_document(
    doc: List[Element],
    chunk_size: int = 2048,
    chunk_overlap: int = 0,
) -> List[DocumentChunk]:

    doc = sorted(doc, key=lambda x: (x.page_n, x.id))

    pointer_to_element: Dict[int, Element] = {}
    paragraphs = []
    for pointer, el in enumerate(doc, start=1):
        paragraphs.append(f"<ID: {pointer}> {el.text}")
        pointer_to_element[pointer] = el

    full_text = "\n\n".join(paragraphs)

    splitter = CharacterTextSplitter(
        separator="\n\n",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        is_separator_regex=False,
    )
    chunks_text = splitter.split_text(full_text)

    chunks = []
    for chunk_text in chunks_text:
        ids = [int(m) for m in re.findall(r"<ID:\s*(\d+)>", chunk_text)]
        elements = [
            pointer_to_element[i] for i in ids if i in pointer_to_element
        ]
        chunks.append(DocumentChunk(content=elements))

    return chunks
