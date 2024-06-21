from langchain_community.document_loaders import FireCrawlLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from groq import Groq

class Pipeline:
    class Valves(BaseModel):
        firecrawl_api_key: str
        groq_api_key: str
        ollama_base_url: str = "http://localhost:11434"
        model: str = "llama3-8b-8192"
        temperature: float = 1.0
        max_tokens: int = 1024
        top_p: float = 1.0

    def __init__(self):
        self.name = "Firecrawl, Groq Llama 3, and Langchain Pipeline"
        self.valves = self.Valves(
            firecrawl_api_key="your_firecrawl_api_key",
            groq_api_key="your_groq_api_key",
        )
        self.vectorstore = None

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        self.groq_client = Groq(api_key=self.valves.groq_api_key)

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        self.groq_client = Groq(api_key=self.valves.groq_api_key)

    async def inlet(self, body: dict, user: dict) -> dict:
        print(f"inlet:{__name__}")
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        print(f"outlet:{__name__}")
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        if body.get("title", False):
            print("Title Generation Request")

        # Load website with Firecrawl
        url = user_message
        loader = FireCrawlLoader(
            api_key=self.valves.firecrawl_api_key,
            url=url,
            mode="crawl",
        )
        docs = loader.load()

        # Setup the Vectorstore
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        self.vectorstore = FAISS.from_documents(documents=splits, embedding=OllamaEmbeddings(base_url=self.valves.ollama_base_url))

        # Retrieval and Generation
        question = user_message
        docs = self.vectorstore.similarity_search(query=question)

        # Generation
        completion = self.groq_client.chat.completions.create(
            model=self.valves.model,
            messages=[
                {
                    "role": "user",
                    "content": f"You are a friendly assistant. Your job is to answer the users question based on the documentation provided below:\nDocs:\n\n{docs}\n\nQuestion: {question}"
                }
            ],
            temperature=self.valves.temperature,
            max_tokens=self.valves.max_tokens,
            top_p=self.valves.top_p,
            stream=False,
            stop=None,
        )
        generated_message = completion.choices[0].message.content.strip()

        return generated_message
