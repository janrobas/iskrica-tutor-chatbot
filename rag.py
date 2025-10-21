from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.docstore.document import Document
from langchain_qdrant import QdrantVectorStore
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM
from langchain.text_splitter import RecursiveCharacterTextSplitter

class RAG:
    def __init__(self, qdrant_url, embedding_model, llama_model):
        self.qdrant_url = qdrant_url
        #self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model, model_kwargs={'device': 'cpu'})
        self.embeddings = HuggingFaceEmbeddings(model_name=embedding_model, model_kwargs={})
        self.llm = OllamaLLM(model=llama_model)

    def split_text_into_chunks(self, texts):
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=50)
        chunks = text_splitter.split_text(texts)
        return chunks
    
    def dodaj(self, text_array, collection_name, force_recreate = True):
        doc_array = []
        for txt in text_array:
            chunks = self.split_text_into_chunks(txt)
            doc_array.extend([Document(page_content=chunk) for chunk in chunks])

        Qdrant.from_documents(
            doc_array,
            self.embeddings,
            url=self.qdrant_url,
            collection_name=collection_name,
            force_recreate=force_recreate
        )
        print("Documents added successfully!")

    def get_retriever(self, collection_name):
        qDrant_vector = QdrantVectorStore.from_existing_collection(
            collection_name=collection_name, 
            url=self.qdrant_url,
            embedding=self.embeddings
        )
        retriever = qDrant_vector.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        return retriever

    def get_chain(self, collection_name):
        """Create and return a retrieval chain for the given collection"""
        retriever = self.get_retriever(collection_name)

        prompt_template = """
        1. Use the context to answer the question.
        2. Don't make up an answer on your own if you don't know it.\n
        3. Keep the answer very short.

        Context: {context}

        Question: {input}

        Answer:"""

        prompt = PromptTemplate.from_template(prompt_template)

        document_chain = create_stuff_documents_chain(
            llm=self.llm,
            prompt=prompt
        )

        retrieval_chain = create_retrieval_chain(
            retriever=retriever,
            combine_docs_chain=document_chain
        )
        
        return retrieval_chain

    def odgovori(self, question, collection_name):
        """Get answer for a question using the specified collection"""
        chain = self.get_chain(collection_name)
        res = chain.invoke({"input": question})
        return {"answer": res["answer"]}
