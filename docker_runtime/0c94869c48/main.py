from langchain.schema import HumanMessage
from langchain.chat_models import ChatOpenAI

def main():
    chat = ChatOpenAI()
    response = chat([HumanMessage(content="hola")])
    print(response.content)

if __name__ == "__main__":
    main()