from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from agents.support.state import State
from agents.support.nodes.conversation.node import conversation
from agents.support.nodes.extractor.node import extractor
from agents.support.nodes.booking.node import booking_node
from agents.support.routes.intent.route import intent_route


def make_graph(config: TypedDict):
    checkpointer = config.get("checkpointer", None)
    builder = StateGraph(State)
    builder.add_node("conversation", conversation)
    builder.add_node("extractor", extractor)
    builder.add_node("booking", booking_node)

    builder.add_edge(START, 'extractor')
    builder.add_conditional_edges('extractor', intent_route)
    builder.add_edge('conversation', END)
    builder.add_edge('booking', END)

    return builder.compile(checkpointer=checkpointer)