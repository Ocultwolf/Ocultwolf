from langgraph.graph import MessagesState
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
import random

llm = init_chat_model("openai:gpt-4o", temperature=1)
file_search_tool = {
    "type": "file_search",
    "vector_store_ids": ["vs_68cf0f0255e481919cd3be25b96c5080"],
}
llm = llm.bind_tools([file_search_tool])

class State(MessagesState):
    customer_name: str
    phone: str
    my_age: str


from pydantic import BaseModel, Field

class ContactInfo(BaseModel):
    """Contact information for a person."""
    name: str = Field(description="The name of the person")
    email: str = Field(description="The email address of the person")
    phone: str = Field(description="The phone number of the person")
    age: str = Field(description="The age of the person")

llm_with_structured_output = init_chat_model("anthropic:claude-3-5-sonnet-20240620", temperature=0)
llm_with_structured_output = llm_with_structured_output.with_structured_output(schema=ContactInfo)

def extractor(state: State):
    history = state["messages"]
    customer_name = state.get("customer_name", None)
    new_state: State = {}
    if customer_name is None or len(history) >= 10:
        schema = llm_with_structured_output.invoke(history)
        new_state["customer_name"] = schema.name
        new_state["phone"] = schema.phone
        new_state["my_age"] = schema.age
    return new_state

def conversation(state: State):
    new_state: State = {}
    history = state["messages"]
    last_message = history[-1]
    customer_name = state.get("customer_name", 'John Doe')
    system_message = f"You are a helpful assistant that can answer questions about the customer {customer_name}"
    ai_message = llm.invoke([("system", system_message), ("user", last_message.text)])
    new_state["messages"] = [ai_message]
    return new_state

from langgraph.graph import StateGraph, START, END

builder = StateGraph(State)
builder.add_node("conversation", conversation)
builder.add_node("extractor", extractor)

builder.add_edge(START, 'extractor')
builder.add_edge('extractor', 'conversation')
builder.add_edge('conversation', END)

agent = builder.compile()



# from langgraph.graph import MessagesState, StateGraph, START, END
# from langchain_core.messages import AIMessage
# from langchain.chat_models import init_chat_model
# from langchain.vectorstores import FAISS
# from langchain.embeddings import OpenAIEmbeddings
# import os

# # =========================
# # CONFIGURACIÓN LLM
# # =========================
# llm = init_chat_model("openai:gpt-4o", temperature=0.7)

# # =========================
# # CONFIGURACIÓN VECTORSTORE
# # =========================
# VECTORSTORE_DIR = "/home/ocultwolf/.openclaw/workspace/python/MongoIA/clon/platzilang/curso-agentes-langgraph/src/agents/vectorstore_openclaw/"
# embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
# vectorstore = FAISS.load_local(VECTORSTORE_DIR, embeddings, allow_dangerous_deserialization=True)

# # =========================
# # FUNCIONES RAG
# # =========================
# def retrieve_context(message):
#     """
#     Recupera contexto relevante de la documentación embebida
#     usando el vectorstore local.
#     """
#     query = message.text
#     retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
#     docs = retriever.invoke(query)  # <-- invoke() es el método correcto
#     return "\n\n".join(d.page_content for d in docs)

# def conversation(state: MessagesState):
#     """
#     Genera la respuesta del asistente usando LLM y contexto RAG.
#     """
#     new_state = {}
#     history = state["messages"]
#     last_message = history[-1]

#     # Recuperamos contexto relevante
#     rag_context = retrieve_context(last_message)

#     # Componemos prompt
#     system_message = f"""
#     Eres un asistente experto que puede responder preguntas
#     usando la documentación local de OpenClaw.

#     Contexto relevante extraído:
#     {rag_context}
#     """

#     # Generamos la respuesta con LLM
#     ai_message = llm.invoke([
#         ("system", system_message),
#         ("user", last_message.text)
#     ])
    
#     new_state["messages"] = [ai_message]
#     return new_state

# # =========================
# # CONSTRUCCIÓN DEL GRAFO DE ESTADO
# # =========================
# builder = StateGraph(MessagesState)
# builder.add_node("conversation", conversation)
# builder.add_edge(START, "conversation")
# builder.add_edge("conversation", END)

# # =========================
# # COMPILACIÓN DEL AGENTE
# # =========================
# rag_agent = builder.compile()