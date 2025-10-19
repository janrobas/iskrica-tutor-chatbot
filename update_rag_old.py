from config import Config
from rag import RAG

def main():
    # Initialize RAG system
    rag = RAG(
        qdrant_url=Config.QDRANT_URL, 
        embedding_model=Config.EMBEDDING_MODEL, 
        llama_model=Config.DEFAULT_LLAMA_MODEL
    )
    
    # Example: Add documents to the collection
    texts = [
        "Name of the professor for AI is Jan. He is also teaching several other courses, like intro to programming. His name is Jan Robas.",
        "The vocational school offers courses in Computer Science, Artificial Intelligence, and Game Development."
    ]
    
    print("Adding documents to vector store...")
    rag.dodaj(text_array=texts, collection_name=Config.DEFAULT_COLLECTION_NAME)
    
    # Example: Query the system
    questions = [
        "What is the name of the professor that teaches programming course?",
        "Who teaches AI?",
        "What courses are offered?"
    ]
    
    print("\nTesting queries:")
    for question in questions:
        print(f"\nQuestion: {question}")
        answer = rag.odgovori(question=question, collection_name=Config.DEFAULT_COLLECTION_NAME)
        print(f"Answer: {answer['answer']}")

if __name__ == "__main__":
    main()