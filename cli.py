# cli.py
import uuid
from agents.simple import agent as simple_agent
from agents.rag import agent as rag_agent
from agents.evaluator import agent as evaluator_agent
from agents.code_review import agent as code_review_agent
from agents.orchestrator import agent as orchestrator_agent
from agents.vector_agent import agent as vector_agent

AGENTS = {
    "simple": simple_agent,
    "rag": rag_agent,
    "evaluator": evaluator_agent,
    "code_review": code_review_agent,
    "orchestrator": orchestrator_agent,
    "vector_agent": vector_agent,
}


def choose_agent():
    print("\n=== Agentes disponibles ===")
    for name in AGENTS.keys():
        print(f"- {name}")
    print("===========================\n")

    while True:
        choice = input("Elige un agente: ").strip()
        if choice in AGENTS:
            return AGENTS[choice], choice
        print("Agente no válido. Intenta de nuevo.")


def choose_vector_model():
    while True:
        choice = input("Elige vector_model ('large' o 'small', default 'large'): ").strip().lower()
        if choice in ["large", "small", ""]:
            return choice if choice else "large"
        print("Opción inválida. Usa 'large' o 'small'.")


def chat_loop(agent, agent_name):
    print(f"\n🚀 Ejecutando agente: {agent_name}")
    print("Escribe 'exit' para salir del chat")
    print("Escribe 'change' para cambiar de agente\n")

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Si es vector_agent, preguntamos modelo
    vector_model = None
    if agent_name == "vector_agent":
        vector_model = choose_vector_model()

    state = {"messages": []}
    if vector_model:
        state["vector_model"] = vector_model

    while True:
        user_input = input("Tú: ")

        if user_input.lower() == "exit":
            return False
        if user_input.lower() == "change":
            return True

        # Agregamos mensaje del usuario como AIMessage
        from langchain_core.messages import AIMessage
        state["messages"].append(AIMessage(content=user_input))

        # Invocamos el agente
        result = agent.invoke(state, config=config)

        # Actualizamos historial
        if "messages" in result:
            state["messages"] = result["messages"]

        # Mostramos última respuesta de forma compatible
        if state["messages"]:
            last_msg = state["messages"][-1]
            if hasattr(last_msg, "content"):  # AIMessage
                print("\nBot:")
                print(last_msg.content)
            elif isinstance(last_msg, dict) and "content" in last_msg:
                print("\nBot:")
                print(last_msg["content"])
            else:
                print("\nBot: [mensaje no reconocido]")
        else:
            print("\nBot: [sin respuesta]")

        print("\n" + "-" * 50 + "\n")


def main():
    print("=== LangGraph Multi-Agent CLI ===")
    while True:
        agent, agent_name = choose_agent()
        change = chat_loop(agent, agent_name)
        if not change:
            break


if __name__ == "__main__":
    main()
