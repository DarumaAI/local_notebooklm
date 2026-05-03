import operator
from typing import Any

from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph.state import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

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

QA_USER = """Context:
{context}

Question:
{question}
"""


class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int


def build_agent(model: Any):
    """Build and return a compiled attributable QA agent for the given LLM."""

    def attributable_llm_call(state: MessagesState) -> MessagesState:
        return {
            "messages": [
                model.invoke(
                    [SystemMessage(content=QA_SYSTEM)] + state["messages"]
                )
            ],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

    builder = StateGraph(MessagesState)
    builder.add_node("attributable_llm_call", attributable_llm_call)
    builder.add_edge(START, "attributable_llm_call")
    builder.add_edge("attributable_llm_call", END)
    return builder.compile()
