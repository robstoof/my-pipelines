from langchain_community.document_loaders import FireCrawlLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
import requests
import openai

class Pipeline:
    class Valves(BaseModel):
        firecrawl_api_key: str
        firecrawl_base_url: str = "http://localhost:5000"
        openai_api_key: str
        openai_api_base: str = "https://api.openai.com/v1"
        ollama_base_url: str = "http://localhost:11434"
        ollama_model: str = "nomic-embed-text"
        openai_model: str = "gpt-3.5-turbo"
        temperature: float = 0.7
        max_tokens: int = 2048
        top_p: float = 0.9
        chunk_size: int = 1000
        chunk_overlap: int = 200

    def __init__(self):
        self.name = "Firecrawl, OpenAI, and Langchain Pipeline"
        self.valves = self.Valves(
            firecrawl_api_key="your_firecrawl_api_key",
            openai_api_key="your_openai_api_key",
        )
        self.vectorstore = None

    async def on_startup(self):
        print(f"on_startup: {self.name}")
        openai.api_key = self.valves.openai_api_key

    async def on_shutdown(self):
        print(f"on_shutdown: {self.name}")

    async def on_valves_updated(self):
        openai.api_key = self.valves.openai_api_key

    async def inlet(self, body: dict, user: dict) -> dict:
        print(f"inlet: {self.name}")
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        print(f"outlet: {self.name}")
        return body

    def load_website(self, url: str) -> List[dict]:
        try:
            loader = FireCrawlLoader(
                api_key=self.valves.firecrawl_api_key,
                url=url,
                mode="crawl",
                base_url=self.valves.firecrawl_base_url
            )
            docs = loader.load()
            print(f"Website loaded successfully: {url}")
            return docs
        except Exception as e:
            print(f"Failed to load website: {e}")
            return []

    def setup_vectorstore(self, docs: List[dict]) -> FAISS:
        try:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.valves.chunk_size, 
                chunk_overlap=self.valves.chunk_overlap
            )
            splits = text_splitter.split_documents(docs)
            vectorstore = FAISS.from_documents(
                documents=splits,
                embedding=OllamaEmbeddings(
                    base_url=self.valves.ollama_base_url,
                    model=self.valves.ollama_model
                )
            )
            print("Vectorstore setup successfully")
            return vectorstore
        except Exception as e:
            print(f"Failed to setup vectorstore: {e}")
            return None

    def retrieve_documents(self, vectorstore: FAISS, query: str) -> List[dict]:
        try:
            docs = vectorstore.similarity_search(query=query)
            print(f"Documents retrieved successfully for query: {query}")
            return docs
        except Exception as e:
            print(f"Failed to retrieve documents: {e}")
            return []

    def generate_response(self, docs: List[dict], question: str) -> str:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a friendly assistant. Your job is to answer the user's question based on the documentation provided below."
                },
                {
                    "role": "user",
                    "content": f"Docs: {docs}\n\nQuestion: {question}"
                }
            ]
            response = openai.ChatCompletion.create(
                model=self.valves.openai_model,
                messages=messages,
                temperature=self.valves.temperature,
                max_tokens=self.valves.max_tokens,
                top_p=self.valves.top_p,
            )
            generated_message = response.choices[0].message["content"].strip()
            print("Response generated successfully")
            return generated_message
        except Exception as e:
            print(f"Failed to generate response: {e}")
            return "Unable to generate a response at this time."

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe: {self.name}")

        if body.get("title", False):
            print("Title Generation Request")

        # Load website
        docs = self.load_website(user_message)
        if not docs:
            return "Failed to load website."

        # Setup vectorstore
        self.vectorstore = self.setup_vectorstore(docs)
        if not self.vectorstore:
            return "Failed to setup vectorstore."

        # Retrieve documents based on user query
        retrieved_docs = self.retrieve_documents(self.vectorstore, user_message)
        if not retrieved_docs:
            return "Failed to retrieve documents."

        # Generate response using OpenAI API
        generated_message = self.generate_response(retrieved_docs, user_message)
        return generated_message