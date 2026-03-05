```python
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage
from langchain.agents import create_agent
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.chains import RetrievalQA
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

def build_conversational_rag_agent(
    persist_directory: str,
    embedding_model_name: str = "text-embedding-ada-002",
    llm_model_name: str = "gpt-4",
    openai_api_key: str = None,
):
    """
    Build a conversational agent with memory based on a FAISS vector store.
    Assumes documents are already embedded and indexed in FAISS under persist_directory.
    If no existing vectorstore is found, you must create and persist it first.

    Args:
        persist_directory: directory with persisted FAISS index + metadata.
        embedding_model_name: OpenAI embedding model to use.
        llm_model_name: OpenAI chat model to use.
        openai_api_key: Optional, set your OpenAI key here or via env var OPENAI_API_KEY

    Returns:
        An agent that supports conversational retrieval with memory.
    """

    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    # Load embeddings model
    embeddings = OpenAIEmbeddings(model=embedding_model_name)

    # Load FAISS vectorstore from disk
    vector_store = FAISS.load_local(persist_directory, embeddings)

    # Create retriever from vectorstore
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})

    # Load chat LLM model with streaming=False for now (can enable streaming as needed)
    llm = ChatOpenAI(model_name=llm_model_name, temperature=0)

    # Build RetrievalQA chain - answers questions based on retrieved docs
    qa_chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)

    # Set up conversation memory to hold history (short term memory)
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

    # System prompt to guide the agent when conversing
    system_prompt = (
        "Eres un agente conversacional que responde preguntas basadas en la documentación.\n"
        "Utiliza la memoria de la conversación para mantener el contexto y obtener información "
        "relevante desde la base de datos vectorial de la documentación."
    )

    # Create a LangChain "tool" for the agent - basically the RetrievalQA chain wrapped
    tools = [{
        "name": "DocumentationQA",
        "description": "Usa esta herramienta para responder preguntas sobre la documentación proporcionando respuestas basadas en la búsqueda en la base de datos vectorial.",
        "func": qa_chain.run
    }]

    # Create the agent with conversational memory and RAG capability
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        memory=memory,
        name="Conversational RAG Agent",
    )

    return agent


if __name__ == "__main__":
    # Ejemplo de uso

    # Ruta donde está almacenado el índice vectorial FAISS (debe existir previamente)
    vectordb_path = "./db_faiss"

    # Crea el agente conversacional
    agent = build_conversational_rag_agent(persist_directory=vectordb_path)

    # Interactúa con el agente
    while True:
        query = input("Tu: ").strip()
        if query.lower() in {"exit", "salir", "quit"}:
            print("Agente: Hasta luego!")
            break

        response = agent.invoke({"messages": [HumanMessage(content=query)]})
        answer = response['messages'][-1].content
        print(f"Agente: {answer}\n")
```