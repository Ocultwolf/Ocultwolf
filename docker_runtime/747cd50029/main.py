```python
from langchain.chat_models import ChatOpenAI
from langchain.agents import create_agent
from langchain.schema import HumanMessage
from langchain.vectorstores import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.chains import RetrievalQA
from langchain.tools import Tool
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os

# Step 1: Build or load your vector store knowledge base with embeddings
def build_vectorstore_from_docs(docs_path: str, persist_directory: str):
    # Load documents from a directory (txt, pdf, etc. can be adapted here)
    loader = DirectoryLoader(docs_path, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()

    # Split documents into chunks for better retrieval
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    docs_split = text_splitter.split_documents(documents)

    # Initialize embeddings
    embeddings = OpenAIEmbeddings()

    # Create FAISS vectorstore
    vectorstore = FAISS.from_documents(docs_split, embeddings)

    # Persist vectorstore locally
    faiss_index_path = os.path.join(persist_directory, "faiss_index")
    os.makedirs(persist_directory, exist_ok=True)
    vectorstore.save_local(faiss_index_path)

    return vectorstore

def load_vectorstore(persist_directory: str) -> FAISS:
    embeddings = OpenAIEmbeddings()
    faiss_index_path = os.path.join(persist_directory, "faiss_index")
    return FAISS.load_local(faiss_index_path, embeddings)

# Step 2: Create a RetrievalQA tool around the vectorstore to answer questions
def create_qa_tool(vectorstore: FAISS, model_name="gpt-4"):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
    llm = ChatOpenAI(model_name=model_name, temperature=0)

    # RetrievalQA chain
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
    )

    # Wrap the chain in a Tool so the agent can call it
    qa_tool = Tool(
        name="DocumentationRetriever",
        func=lambda q: qa_chain.run(q),
        description=(
            "Use this tool to answer questions ABOUT THE DOCUMENTATION. "
            "Input should be a question related to the documentation."
        )
    )
    return qa_tool

# Step 3: Create an Agent that uses the QA tool over the vectorstore
def create_documentation_agent(qa_tool: Tool, model_name="gpt-4"):
    llm = ChatOpenAI(model_name=model_name, temperature=0)

    system_prompt = (
        "You are an intelligent assistant agent that answers questions using the documentation."
        "Use the provided tool to look up relevant answers grounded in the documentation."
    )

    # Create an agent with the tool available
    agent = create_agent(
        model=llm,
        tools=[qa_tool],
        system_prompt=system_prompt,
        name="Documentation QA Agent",
    )
    return agent

# === USAGE EXAMPLE ===
if __name__ == "__main__":
    # Paths
    DOCUMENTS_PATH = "./docs"  # Folder with documentation text files
    PERSIST_DIR = "./vectorstore"

    # Build vectorstore once (uncomment if vectorstore not built)
    # vectorstore = build_vectorstore_from_docs(DOCUMENTS_PATH, PERSIST_DIR)

    # Or load existing vectorstore from disk
    vectorstore = load_vectorstore(PERSIST_DIR)

    # Create QA tool
    qa_tool = create_qa_tool(vectorstore)

    # Create agent
    agent = create_documentation_agent(qa_tool)

    # Example user question about the documentation
    user_question = "¿Cómo puedo instalar y configurar el sistema?"

    # Invoke the agent with the question wrapped in HumanMessage
    response = agent.invoke({"messages": [HumanMessage(content=user_question)]})

    print("Respuesta del agente:")
    print(response["messages"][-1].content)
```
