import os
import uuid
from langchain.agents import create_agent
from langchain.backend import (
    CompositeBackend,
    StoreBackend,
    StateBackend,
    InMemoryStore,
)
from langchain.callbacks import SkillMiddleware
from langchain.checkpoints import InMemorySaver
from langchain.llms import OpenAI
from langchain.vectorstores import LocalVectorStore
from langchain.embeddings.openai import OpenAIEmbeddings

# Configuration - adjust paths and API keys accordingly
VECTORSTORE_PATH = "./local_vectorstore"  # Folder where your vector DB is saved locally
EMBEDDING_MODEL_NAME = "text-embedding-ada-002"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

# Initialize the OpenAI LLM and embedding model
llm = OpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY)
embedding_model = OpenAIEmbeddings(
    model=EMBEDDING_MODEL_NAME, openai_api_key=OPENAI_API_KEY
)

# Load local vector database stored in VECTORSTORE_PATH using the embedding model
vectorstore = LocalVectorStore.load(VECTORSTORE_PATH, embedding=embedding_model)


# Tool function: semantic search in your vector DB and answer generation
def vectorstore_qa_tool(query: str) -> str:
    # Retrieve top relevant documents from the vectorstore
    docs = vectorstore.similarity_search(query, k=5)

    # Combine retrieved docs content for the prompt context
    context = "\n\n".join([doc.page_content for doc in docs])

    prompt = (
        f"You are a helpful conversational agent with access to the following knowledge snippets:\n"
        f"{context}\n\n"
        f"Answer the following question based on the above information:\n{query}"
    )

    # Ask the LLM to answer using the retrieved context
    response = llm.invoke({"messages": [{"role": "user", "content": prompt}]})
    return response["messages"][-1]["content"]


# Compose system prompt for conversation with memory and vectorsearch
system_prompt = (
    "You are a conversational agent with long-term memory and access to a local vector database for knowledge retrieval.\n"
    "- Answer user questions by searching the vector database embeddings first.\n"
    "- Use the retrieved documents to formulate accurate and complete answers.\n"
    "- Keep the conversation context in memory and use it to improve responses.\n"
    "- Save conversation memory persistently to continue context across interactions."
)

# Setup backend: use a composite backend that persists memories (state + file storage)
backend_factory = lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={"/memories/": StoreBackend(rt)},
)

# Create the agent with:
# - the LLM
# - system prompt (to instruct behavior)
# - SkillMiddleware for extensibility
# - InMemorySaver for checkpointing conversation state
agent = create_agent(
    llm,
    system_prompt=system_prompt,
    middleware=[SkillMiddleware()],
    checkpointer=InMemorySaver(),
    backend=backend_factory
)

# Inject our vectorstore_qa_tool into the agent's skills manually for now:
# The agent must be able to call this tool to retrieve knowledge from the vector DB
from langchain.agents import Skill

vectorsearch_skill = Skill(
    id="vectorsearch",
    description="Search your local vector database and answer questions",
    func=vectorstore_qa_tool,
)

agent.middleware[0].register_skill(vectorsearch_skill)


def main():
    thread_id = str(uuid.uuid4())  # Unique conversation thread ID to keep memory isolated
    config = {"configurable": {"thread_id": thread_id}}

    print("Conversational agent with vector store retrieval. Type your questions.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        user_input = input("User: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Exiting. Goodbye!")
            break

        # Invoke the agent with user message and memory config
        result = agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]}, config=config
        )

        # Print agent's answer
        for message in result["messages"]:
            if message["role"] == "assistant":
                print(f"Agent: {message['content']}")


if __name__ == "__main__":
    main()