# vector_agent.py
from langgraph.graph import MessagesState, StateGraph, START, END
from langchain_core.messages import AIMessage
from langchain.chat_models import init_chat_model
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# =========================
# Inicializamos LLM
# =========================
llm_large = init_chat_model("openai:gpt-4o", temperature=0.2)
llm_small = init_chat_model("openai:gpt-3.5-turbo", temperature=0.5)

# =========================
# Cargamos vectorstores locales
# =========================
vectorstore_large = FAISS.load_local(
    "src/agents/vectorstore_langchain_langgraph",
    OpenAIEmbeddings(model="text-embedding-3-large"),
    allow_dangerous_deserialization=True
)

vectorstore_small = FAISS.load_local(
    "src/agents/vectorstore_openclaw",
    OpenAIEmbeddings(model="text-embedding-3-small"),
    allow_dangerous_deserialization=True
)

# =========================
# Estado
# =========================
class State(MessagesState):
    vector_model: str = "large"  # Por defecto "large"

# =========================
# Nodo principal
# =========================
def vector_node(state: State):
    new_state: State = {}

    # Elegimos vectorstore y LLM según state["vector_model"]
    model_choice = state.get("vector_model", "large")
    if model_choice == "large":
        vectorstore = vectorstore_large
        llm = llm_large
    else:
        vectorstore = vectorstore_small
        llm = llm_small

    # Tomamos último mensaje del usuario
    history = state.get("messages", [])
    if not history:
        last_user_message = "Hola"
    else:
        last_user_message = history[-1].content

    # Buscamos en vectorstore
    docs = vectorstore.as_retriever(search_kwargs={"k": 4}).invoke(last_user_message)
    context = "\n\n".join([doc.page_content for doc in docs])

    # Creamos prompt
    prompt = f"""
Usa esta información para responder la pregunta de forma clara:

{context}

Pregunta:
{last_user_message}
"""

    # Generamos respuesta
    ai_message = llm.invoke(history + [prompt])
    new_state["messages"] = [ai_message]

    return new_state

# =========================
# Construcción del grafo
# =========================
builder = StateGraph(State)
builder.add_node("vector_node", vector_node)
builder.add_edge(START, "vector_node")
builder.add_edge("vector_node", END)

agent = builder.compile()
