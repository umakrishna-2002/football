import os
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

WIKI_DIR = "data/wikipedia"
CHROMA_DIR = "vectordb"

model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection("football_knowledge")

splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

def load_and_chunk():
    files = [f for f in os.listdir(WIKI_DIR) if f.endswith(".txt")]
    total_chunks = 0

    for filename in files:
        filepath = os.path.join(WIKI_DIR, filename)
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        # Extract metadata from first two lines
        lines = content.split("\n")
        title = lines[0].replace("TITLE: ", "").strip()
        category = lines[1].replace("CATEGORY: ", "").strip()
        text = "\n".join(lines[3:])  # skip header lines

        chunks = splitter.split_text(text)

        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk).tolist()
            collection.add(
                ids=[f"{filename}_{i}"],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "title": title,
                    "title_lower": title.lower(),  # for case-insensitive matching
                    "category": category,
                    "source": filename
                }]
            )
        total_chunks += len(chunks)
        print(f"Indexed: {title} — {len(chunks)} chunks")

    print(f"\nDone. {total_chunks} total chunks stored in ChromaDB")

if __name__ == "__main__":
    load_and_chunk()
