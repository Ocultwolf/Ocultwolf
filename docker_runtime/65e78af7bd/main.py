```python
"""
agent.py

LangChain agent to scrape webpages, save a local copy on a server, and serve the pages.

The agent:
- Scrapes the provided URL.
- Saves the HTML content to a server folder (organized by domain).
- Serves the saved copies via a minimal FastAPI server.

Usage:
    Run the FastAPI server:
        uvicorn agent:app --reload

    Use the agent to scrape and copy websites programmatically,
    or extend to accept commands via LLM (integration point shown).

Requirements:
    pip install langchain requests beautifulsoup4 fastapi uvicorn aiofiles python-multipart

Environment:
    Set OPENAI_API_KEY or other LLM key if you want to integrate LLM features.
"""

import os
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from langchain.agents import create_openai_functions_agent
from langchain.chat_models import ChatOpenAI

# Constants
SITES_ROOT = "./copied_sites"

# Ensure the base directory exists
os.makedirs(SITES_ROOT, exist_ok=True)

app = FastAPI(
    title="Website Scraper & Server Agent",
    description="An agent that scrapes, copies, stores and serves webpages.",
    version="1.0",
)


def sanitize_filename(name: str) -> str:
    """
    Sanitize filenames and directory names to a safe form.
    """
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)


def domain_from_url(url: str) -> str:
    """
    Extract domain from url for folder naming.
    """
    parsed = urlparse(url)
    domain = parsed.netloc
    return sanitize_filename(domain)


def scrape_website(url: str) -> str:
    """
    Scrape webpage content (HTML) from a URL.

    Raises HTTPError if request fails.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (LangChain Agent - Python)"
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()

    # Optionally, process with BeautifulSoup to prettify or clean if desired
    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove scripts & styles for a cleaner saved page if you want:
    for script in soup(["script", "style"]):
        script.decompose()
    return str(soup)


def save_html_content(domain: str, url: str, html: str) -> str:
    """
    Save HTML content to a file under the domain folder.

    Filename is a sanitized path + .html

    Returns the filesystem path of the saved file.
    """
    domain_dir = os.path.join(SITES_ROOT, domain)
    os.makedirs(domain_dir, exist_ok=True)

    # Convert url path and query to safe filename
    parsed = urlparse(url)
    # Use path+query with slashes replaced to underscore
    path_name = parsed.path.strip("/")
    if not path_name:
        path_name = "index"
    else:
        # Remove trailing slashes
        path_name = path_name.rstrip("/").replace("/", "_")

    if parsed.query:
        # Append query string sanitized
        query_s = sanitize_filename(parsed.query)
        path_name = f"{path_name}_{query_s}"
    filename = f"{path_name}.html"

    file_path = os.path.join(domain_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    return file_path


@app.post("/scrape_and_copy", summary="Scrapes and copies a website page")
async def scrape_and_copy(url: str):
    """
    Scrape a URL, save a copy on server, and return storage path and accessible URL.
    """
    try:
        domain = domain_from_url(url)
        html = await asyncio.to_thread(scrape_website, url)
        file_path = await asyncio.to_thread(save_html_content, domain, url, html)

        # Return the URL to access saved page via our server
        accessible_url = f"/sites/{domain}/{os.path.basename(file_path)}"

        return {
            "status": "success",
            "message": f"Scraped and saved {url}",
            "file_path": file_path,
            "accessible_url": accessible_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount the saved sites folder as static files
app.mount("/sites", StaticFiles(directory=SITES_ROOT, html=True), name="sites")


# Optional: Basic home endpoint
@app.get("/", response_class=HTMLResponse)
async def homepage():
    return """
    <html>
        <head><title>LangChain Website Scraper Agent</title></head>
        <body>
            <h1>LangChain Website Scraper Agent</h1>
            <p>Use POST /scrape_and_copy with JSON body { "url": "http://example.com" } to scrape and save sites.</p>
            <p>Saved sites are accessible under /sites/&lt;domain&gt;/&lt;page&gt;</p>
        </body>
    </html>
    """


# Example integration with LangChain agent using openai-functions agent (optional)
# This shows how to integrate the scraping functionality as a callable tool for the agent.

def langchain_scrape_tool(url: str) -> str:
    """Wrap scraping function for agent use."""
    domain = domain_from_url(url)
    html = scrape_website(url)
    file_path = save_html_content(domain, url, html)
    return f"Scraped and saved at {file_path}, accessible at /sites/{domain}/{os.path.basename(file_path)}"


# Define an OpenAI-backed agent with one tool: scrape_website
llm = ChatOpenAI(temperature=0)

functions = [
    {
        "name": "scrape_website",
        "description": "Scrape a website and store a local copy",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL of the website page to scrape",
                }
            },
            "required": ["url"],
        },
    }
]

def scrape_website_function(params: dict) -> str:
    url = params.get("url")
    if not url:
        return "Error: No URL provided."
    try:
        return langchain_scrape_tool(url)
    except Exception as e:
        return f"Error scraping website: {e}"


agent = create_openai_functions_agent(
    llm=llm,
    functions=[("scrape_website", scrape_website_function)],
)


# Example agent usage (commented out):
# result = agent.invoke("Scrapea esta pagina: https://example.com")
# print(result)

# --------------------
# To run the server and make requests:
# uvicorn agent:app --reload
#
# Then post JSON like {"url": "https://example.com"} to http://127.0.0.1:8000/scrape_and_copy
# and visit http://127.0.0.1:8000/sites/example.com/index.html to see saved copy.
# --------------------
```