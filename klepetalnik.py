import time
from langchain_community.llms import Ollama
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import StrOutputParser
from langchain.schema.runnable import Runnable
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
        # Override to prevent default "using Ollama" message
        pass

    async def on_llm_start(self, serialized, prompts, **kwargs):
        # Optional: Add custom loading message if needed
        #await cl.Message(content="Hmmm...").send()
        pass

@cl.password_auth_callback
def auth_callback(username: str, password: str):
    # Fetch the user matching username from your database
    # and compare the hashed password with the value stored in the database
    if (authenticate(username, password)):
        return cl.User(
            identifier=username.upper(), metadata={"role": "admin", "provider": "credentials", "mode": get_code(password).get("mode", "pro1")}
        )
    else:
        return None

def get_settings(mode: str):
    with open("nastavitve.json", "r") as f:
        return json.load(f)[mode]

@cl.on_chat_start
async def on_chat_start():
    user = cl.user_session.get("user")
    mode = user.metadata.get("mode", "default")  # Add default fallback if needed
    
    settings = get_settings(mode)

    rag_collection_name = settings.get("rag_collection_name", Config.DEFAULT_COLLECTION_NAME)
    cl.user_session.set("rag_collection_name", rag_collection_name)

    rag = RAG(
        qdrant_url=Config.QDRANT_URL,
        embedding_model=Config.EMBEDDING_MODEL, 
        llama_model=settings.get("model", Config.DEFAULT_LLAMA_MODEL) 
    )
    #rag.dodaj(text_array=["Moje ime je Jan Robas. Kadarkoli kdorkoli vpraša za ime sistema, napiši Jan Robas.", "Tole je slovenska himna: Živé naj vsi naródi, ki hrepené dočakat' dan, da koder sonce hodi, prepir iz svéta bo pregnan, da rojak prost bo vsak, ne vrag, le sosed bo mejak!"], collection_name=rag_collection_name)
    cl.user_session.set("rag", rag)

    model = Ollama(
        model=settings.get("model", Config.DEFAULT_LLAMA_MODEL),
        temperature=settings.get("temperature", 0.3),
        top_p=settings.get("top_p", 0.8),
        top_k=settings.get("top_k", 50),
        repeat_penalty=settings.get("repeat_penalty", 1.1),
        num_ctx=settings.get("num_ctx", 2048)
    )

    #history = cl.user_session.get("history", [])

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                settings.get("prompt", "")
            ),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )
    runnable = prompt | model | StrOutputParser()
    cl.user_session.set("thinking", settings.get("thinking", True))
    cl.user_session.set("runnable", runnable)
    cl.user_session.set("model", model)
    cl.user_session.set("history", [])

MAX_HISTORY = 8
#@cl.on_message
async def on_message(message: cl.Message):
    # config = {"configurable": {"thread_id": cl.context.session.id}}

    with open("debugx.log", "a", encoding="utf-8") as file:
        file.write(f"{cl.user_session.get("user").identifier}: {message.content}\n")

    runnable = cl.user_session.get("runnable")
    history = cl.user_session.get("history")

    msg = cl.Message(content="")

    inputs = {
        "question": message.content,
        "history": history
    }

    async for chunk in runnable.astream(
        # {"question": message.content},
        inputs,
        config=RunnableConfig(callbacks=[CustomCallbackHandler()]),
    ):
        await msg.stream_token(chunk)

    await msg.send()

    new_history = [
        *history,
        HumanMessage(content=message.content),
        AIMessage(content=msg.content)
    ][-MAX_HISTORY:]
    cl.user_session.set("history", new_history)
#https://github.com/Chainlit/cookbook/blob/main/deepseek-r1/ollama.py

@cl.on_message
async def on_message(message: cl.Message):
    start_time = time.time()
    
    with open("debugx.log", "a", encoding="utf-8") as file:
        file.write(f"{cl.user_session.get('user').identifier}: {message.content}\n")

    runnable = cl.user_session.get("runnable")
    history = cl.user_session.get("history")
    thinking = cl.user_session.get("thinking")
    rag_collection_name = cl.user_session.get("rag_collection_name")
    rag = cl.user_session.get("rag")
    model = cl.user_session.get("model")

    try:
        rag_result = rag.odgovori(message.content, rag_collection_name)
        context_answer = rag_result["answer"]
        
        # Create enhanced system prompt
        enhanced_system_prompt = f"{message.content}\n\nAdditional Context from knowledge base: {context_answer}"
        
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get("user").identifier}: YES {enhanced_system_prompt}\n")
        # Create a temporary runnable with enhanced context
        enhanced_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", enhanced_system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )
        enhanced_runnable = enhanced_prompt | model | StrOutputParser()
        
        # Use enhanced runnable for this message only
        current_runnable = enhanced_runnable
    except Exception as e:
        
        with open("debugx.log", "a", encoding="utf-8") as file:
            file.write(f"{cl.user_session.get("user").identifier}: CRAPPP {e}\n")
        # Use regular runnable if RAG fails
        print("RAG fail")
        current_runnable = runnable
        enhanced_question = message.content

    inputs = {
        "question": message.content,
        "history": history
    }

    # Initialize the stream correctly
    # stream = runnable.astream(
    #     inputs,
    #     config=RunnableConfig(callbacks=[CustomCallbackHandler()]),
    # )
    stream = current_runnable.astream(  # ← Change this line
        inputs,
        config=RunnableConfig(callbacks=[CustomCallbackHandler()]),
    )
    thinking = False
    thought_content = []

    async with cl.Step(name="Premišljujem", type="Iskrica") as thinking_step:
    #async with cl.Step(name="Thinking", type="llm") as thinking_step:
        final_answer = cl.Message(content="")
        await final_answer.send()

        # Style the thinking indicator
        thinking_step.elements = [
            # cl.Text(
            #     content="Processing...",
            #     display="inline",
            #     style="color: #666; font-size: 0.9em; font-style: italic;"
            # )
        ]
        thinking_step.name = f"Premišljujem"

        async for chunk in stream:
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

    # Update history
    new_history = [
        *history,
        HumanMessage(content=message.content),
        AIMessage(content=final_answer.content)
    ][-MAX_HISTORY:]
    cl.user_session.set("history", new_history)
