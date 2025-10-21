import time
import asyncio
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import StrOutputParser
from langchain.schema.runnable import Runnable, RunnablePassthrough, RunnableLambda
from langchain.schema.runnable.config import RunnableConfig
import chainlit as cl
from typing import Optional
from auth import authenticate, get_code
from langchain_core.messages import HumanMessage, AIMessage
from langchain.callbacks.base import BaseCallbackHandler
import json
from chainlit.config import config
from rag import RAG
from config import Config
from history_compressor import SmartHistoryCompressor

class CustomCallbackHandler(BaseCallbackHandler):
    async def on_chain_start(self, serialized, inputs, **kwargs):
        pass

    async def on_llm_start(self, serialized, prompts, **kwargs):
        pass

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if (authenticate(username, password)):
        return cl.User(
            identifier=username.upper(), 
            metadata={
                "role": "admin", 
                "provider": "credentials", 
                "mode": get_code(password).get("mode", "pro1")
            }
        )
    else:
        return None

def get_settings(mode: str):
    with open("nastavitve.json", "r") as f:
        return json.load(f)[mode]

@cl.on_chat_start
async def on_chat_start():
    user = cl.user_session.get("user")
    mode = user.metadata.get("mode", "default")  
    
    settings = get_settings(mode)

    rag_collection_name = settings.get("rag_collection_name", Config.DEFAULT_COLLECTION_NAME)
    cl.user_session.set("rag_collection_name", rag_collection_name)

    rag = RAG(
        qdrant_url=Config.QDRANT_URL,
        embedding_model=Config.EMBEDDING_MODEL, 
        llama_model=settings.get("model", Config.DEFAULT_LLAMA_MODEL),
    )
    cl.user_session.set("rag", rag)

    # Main model for responses
    model = Ollama(
        model=settings.get("model", Config.DEFAULT_LLAMA_MODEL),
        temperature=settings.get("temperature", 0.3),
        top_p=settings.get("top_p", 0.8),
        top_k=settings.get("top_k", 50),
        repeat_penalty=settings.get("repeat_penalty", 1.1),
        num_ctx=settings.get("num_ctx", 2048),
        timeout=120.0
    )

    # Separate model for compression (smaller & faster)
    compression_model = Ollama(
        model="llama3.1:8b",  # Smaller model for compression
        temperature=0.1,      # Lower temperature for consistent summaries
        top_p=0.9,
        top_k=40,
        repeat_penalty=1.0,
        num_ctx=1024,         # Smaller context for summaries
        timeout=30.0          # Shorter timeout for compression
    )

    # Initialize smart history compressor
    history_compressor = SmartHistoryCompressor(
        compression_model=compression_model,
        max_raw_history=3,
        compression_threshold=3,
        compression_batch_size=3
    )
    cl.user_session.set("history_compressor", history_compressor)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system", 
            settings.get("prompt", "") + 
            "\n\nConversation Context - what we have talked about:\n{conversation_context}\n\n" +
            "Trenutno vprašanje uporabnika je zadnje sporočilo v pogovoru! Odgovori na to vprašanje."
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ])
    
    runnable = prompt | model | StrOutputParser()
    
    cl.user_session.set("thinking", settings.get("thinking", True))
    cl.user_session.set("runnable", runnable)
    cl.user_session.set("model", model)
    cl.user_session.set("compression_model", compression_model)

@cl.on_message
async def on_message(message: cl.Message):
    start_time = time.time()
    
    with open("debugx.log", "a", encoding="utf-8") as file:
        file.write(f"{cl.user_session.get('user').identifier}: {message.content}\n")

    runnable = cl.user_session.get("runnable")
    thinking = cl.user_session.get("thinking")
    rag = cl.user_session.get("rag")
    rag_collection_name = cl.user_session.get("rag_collection_name")
    history_compressor = cl.user_session.get("history_compressor")

    # Get RAG context
    context = ""
    try:
        retriever = rag.get_retriever(rag_collection_name)
        
        # Get documents
        docs = retriever.get_relevant_documents(message.content)
        
        # Combine documents
        if docs:
            context_parts = []
            for i, doc in enumerate(docs, 1):
                context_parts.append(f"{i}. {doc.page_content}")
            context = "\n".join(context_parts).strip()
            
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: RAG_CONTEXT - Found {len(docs)} documents\n")

    except Exception as e:
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: RAG_FAILED - {e}\n")

    # Add context to question
    if context:
        enhanced_question = f"Please use the following context to answer the question. If the context is not relevant, use your own knowledge. Context is automatically added - do not mention the context in the answer, it would confuse the user.\n\nContext:\n{context}\n\nQuestion: {message.content}"

        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: ENHANCED_QUESTION - Using context\n")
    else:
        enhanced_question = message.content

    # Get conversation context from compressor
    conversation_context = history_compressor.get_conversation_context()
    message_history = history_compressor.get_message_history()

    # Log current conversation state for debugging
    with open("debugx.log", "a", encoding="utf-8") as file:
        stats = history_compressor.get_stats()
        file.write(f"{cl.user_session.get('user').identifier}: CONV_STATS - {stats}\n")
        if history_compressor.raw_history:
            last_question = history_compressor.raw_history[-1]["question"][:100]
            file.write(f"{cl.user_session.get('user').identifier}: LAST_QUESTION - {last_question}...\n")
            file.write(f"{cl.user_session.get('user').identifier}: CONTEXT - {conversation_context}...\n")

    inputs = {
        "question": enhanced_question,
        "history": message_history,
        "conversation_context": conversation_context
    }

    # Stream response
    try:
        stream = runnable.astream(
            inputs,
            config=RunnableConfig(callbacks=[CustomCallbackHandler()]),
        )

        thinking = False
        thought_content = []
        full_response = ""


        async with cl.Step(name="Premišljujem", type="Iskrica") as thinking_step:
            final_answer = cl.Message(content="")
            await final_answer.send()

            thinking_step.elements = []
            thinking_step.name = f"Premišljujem"

            async for chunk in stream:
                # Handle both string output and dict output from different chain types
                if isinstance(chunk, dict):
                    # For retrieval chain, extract the answer
                    content = chunk.get("answer", str(chunk))
                else:
                    content = chunk
                
                if content == "<think>":
                    thinking = True
                    continue
                elif content == "</think>":
                    thinking = False
                    continue

                if thinking:
                    thought_content.append(content)
                    thinking_step.name = f"Premišljujem: {len(thought_content)}"
                    await thinking_step.stream_token(content)
                    await thinking_step.update()
                else:
                    await final_answer.stream_token(content)
                    
            await final_answer.update()
            await thinking_step.update()

        # Update history compressor with new exchange (ASYNC CALL)
        await history_compressor.add_exchange(message.content, final_answer.content)
        
        # Log updated statistics
        updated_stats = history_compressor.get_stats()
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: UPDATED_STATS - {updated_stats}\n")
            file.write(f"{cl.user_session.get('user').identifier}: RESPONSE_SUCCESS - {full_response[:200]}...\n")
        
    except Exception as e:
        error_msg = f"Error processing your request: {str(e)}"
        await cl.Message(content=error_msg).send()
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: STREAM_ERROR - {e}\n")
