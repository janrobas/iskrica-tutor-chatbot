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

    model = Ollama(
        model=settings.get("model", Config.DEFAULT_LLAMA_MODEL),
        temperature=settings.get("temperature", 0.3),
        top_p=settings.get("top_p", 0.8),
        top_k=settings.get("top_k", 50),
        repeat_penalty=settings.get("repeat_penalty", 1.1),
        num_ctx=settings.get("num_ctx", 2048),
        timeout=120.0
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", settings.get("prompt", "") + "\n\nTrenutno vprašanje uporabnika je zadnje sporočilo v pogovoru! Odgovori na to vprašanje."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ])
    
    runnable = prompt | model | StrOutputParser()
    
    cl.user_session.set("thinking", settings.get("thinking", True))
    cl.user_session.set("runnable", runnable)
    cl.user_session.set("model", model)
    cl.user_session.set("history", [])

MAX_HISTORY = 8

@cl.on_message
async def on_message(message: cl.Message):
    start_time = time.time()
    
    with open("debugx.log", "a", encoding="utf-8") as file:
        file.write(f"{cl.user_session.get('user').identifier}: {message.content}\n")

    runnable = cl.user_session.get("runnable")
    history = cl.user_session.get("history")
    thinking = cl.user_session.get("thinking")
    rag = cl.user_session.get("rag")
    rag_collection_name = cl.user_session.get("rag_collection_name")

    context = ""
    try:
        retriever = rag.get_retriever(rag_collection_name)
        
        # pridobi dokumente
        docs = retriever.get_relevant_documents(message.content)
        
        # združi dokumente
        if docs:
            context_parts = []
            for i, doc in enumerate(docs, 1):
                context_parts.append(f"{i}. {doc.page_content}")
            context = "\n".join(context_parts).strip()
            
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: RAG_CONTEXT - Found {len(docs)} documents\n")
            file.write(f"{cl.user_session.get('user').identifier}: RAG_CONTEXT - Content: {context}\n")

    except Exception as e:
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: RAG_FAILED - {e}\n")

    # dodaj kontekst
    if context:
        enhanced_question = f"Please use the following context to answer the question. If the context is not relevant, use your own knowledge.\n\nContext:\n{context}\n\nQuestion: {message.content}"

        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: ENHANCED_QUESTION - Using context\n")
    else:
        enhanced_question = message.content

    inputs = {
        "question": enhanced_question,
        "history": history
    }

    # stream response
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
            thinking_step.name = "Premišljujem"

            async for chunk in stream:
                content = str(chunk)
                
                full_response += content
                
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

        # update history
        new_history = [
            *history,
            HumanMessage(content=message.content),
            AIMessage(content=final_answer.content)
        ][-MAX_HISTORY:]
        cl.user_session.set("history", new_history)
        
        # log
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: RESPONSE_SUCCESS - {full_response[:200]}...\n")
        
    except Exception as e:
        error_msg = f"Error processing your request: {str(e)}"
        await cl.Message(content=error_msg).send()
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get('user').identifier}: STREAM_ERROR - {e}\n")
