import requests
import time
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

BASE_URL = "https://docs.openclaw.ai/"
DOMAIN = urlparse(BASE_URL).netloc

visited = set()
documents = []

def clean_text(soup):
    # Eliminar scripts, estilos y navegación innecesaria
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    main = soup.find("main") or soup.body
    if not main:
        return ""

    text = main.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)

def crawl(url):
    if url in visited:
        return
    if urlparse(url).netloc != DOMAIN:
        return

    print(f"🔎 Crawling: {url}")
    visited.add(url)

    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return
    except Exception:
        return

    soup = BeautifulSoup(r.text, "html.parser")
    cleaned = clean_text(soup)

    if cleaned:
        documents.append({
            "url": url,
            "text": cleaned
        })

    # Buscar enlaces internos
    for link in soup.find_all("a", href=True):
        next_url = urljoin(BASE_URL, link["href"])
        if next_url not in visited and urlparse(next_url).netloc == DOMAIN:
            crawl(next_url)

    time.sleep(0.3)

def build_vectorstore():
    print("✂️ Dividiendo en chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    texts = []
    metadatas = []

    for doc in documents:
        chunks = splitter.split_text(doc["text"])
        for chunk in chunks:
            texts.append(chunk)
            metadatas.append({"source": doc["url"]})

    print(f"📄 Total chunks: {len(texts)}")

    print("🧠 Generando embeddings...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    vectorstore = FAISS.from_texts(
        texts,
        embedding=embeddings,
        metadatas=metadatas
    )

    vectorstore.save_local("openclaw_faiss_index")
    print("✅ Índice guardado en ./openclaw_faiss_index")

if __name__ == "__main__":
    print("🚀 Iniciando scraping completo de OpenClaw Docs")
    crawl(BASE_URL)
    print(f"📚 Páginas recopiladas: {len(documents)}")
    build_vectorstore()
