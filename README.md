# Klepetalnik - Smart Programming Tutor Chatbot

An intelligent chatbot system that combines RAG (Retrieval-Augmented Generation) with smart conversation history compression to provide personalized programming tutoring.
This is a project in vocational school that enables us to create custom chatbots for students and run them locally.
At this point, this is quite a mess with some parts coded manually and some parts partially vibe coded with so much back-and-forth that it was probably not worth it.
In the future, I hope to clean this up a bit to make it more useful for everybody else. I think the smart history compressor makes a lot of sense and this is something that is worth researching.

## Prerequisites

- Python 3.8+
- [Docker](https://docker.com) installed and running
- [Ollama](https://ollama.ai/) installed and running
- Required Ollama models pulled (see Configuration)

## Quick Start

1. **Start Qdrant vector database:**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

2. **Install Python dependencies:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up environment:**
```bash
cp .env.sample .env
# Edit .env with your settings
```

4. **Run the chatbot:**
```bash
chainlit run klepetalnik.py
```

## Features

- **Smart History Compression**: Automatically compresses conversation history to maintain context without exceeding token limits
- **RAG Integration**: Enhances responses with relevant knowledge from your document collections
- **Multiple User Modes**: Different configurations for various user types (pro1, generic)
- **Authentication**: Simple password-based authentication with mode-based settings
- **Streaming Responses**: Real-time response streaming with thinking steps
- **Ollama Integration**: Local LLM processing for privacy and control

## Installation

### 1. Set up Qdrant Vector Database

```bash
# Pull and run Qdrant in Docker
docker run -p 6333:6333 qdrant/qdrant
```

Qdrant will be available at `http://localhost:6333`

### 2. Python Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file:
```env
QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
DEFAULT_LLAMA_MODEL=gemma3:27b
DEFAULT_COLLECTION_NAME=programiranje
```

### 4. Download Ollama Models

```bash
# Base models
ollama pull gemma3:27b
ollama pull llama3.1:8b

# Optional: For pro1 mode
ollama pull deepseek-r1:32b
```

### 5. Authentication Setup

Create `kode.json` based on `kode.sample.json`:
```json
[
  {
    "name": "teacher",
    "code": "teacher123",
    "mode": "pro1"
  },
  {
    "name": "student",
    "code": "student123", 
    "mode": "generic"
  }
]
```

## Configuration

### Model Settings (`nastavitve.json`)

The system supports multiple modes with different configurations:

**pro1 mode** (Programming Tutor):
- Uses `deepseek-r1:32b` model
- Strict programming tutoring rules
- Focus on C# programming guidance
- Encourages problem-solving over complete solutions

**generic mode** (General Chat):
- Uses `gemma3:27b` model  
- General conversational AI
- Slovenian language focus
- Relaxed response style

### Customizing Modes

Edit `nastavitve.json` to modify existing modes or add new ones:

```json
{
  "your_mode": {
    "name": "your_mode",
    "temperature": 0.3,
    "top_p": 0.8,
    "model": "your-model",
    "prompt": "Your custom system prompt...",
    "thinking": true,
    "rag_collection_name": "your_collection"
  }
}
```

## Running the Application

1. **Start the chatbot:**
```bash
chainlit run klepetalnik.py
```

2. **Access the interface:**
Open `http://localhost:8000` in your browser

3. **Login:**
Use credentials from your `kode.json` file:
- Username: any name (for display purposes)
- Password: the corresponding code from `kode.json`

## Setting up RAG Knowledge Base

### Creating Document Collections

1. **Prepare your documents** in a JSON array format:
```json
[
  "C# is an object-oriented programming language...",
  "Arrays in C# are zero-indexed collections...",
  "Methods should follow the Single Responsibility Principle..."
]
```

2. **Add documents to RAG collection:**
```bash
python update_rag.py documents.json your_collection_name
```

### Available RAG Collections

- `programiranje` - General programming concepts
- Create custom collections for specific topics

## How It Works

### Smart History Compression

The system automatically manages conversation history:

- **Raw History**: Keeps recent 3 exchanges uncompressed for immediate context
- **Compression**: When threshold is reached, compresses old exchanges into a summary
- **Single Summary**: Maintains one evolving summary that gets updated incrementally
- **Context Preservation**: New compressions include previous summary context

### Conversation Flow

1. User asks a question
2. System retrieves relevant context from RAG and injects it in the prompt
3. Compressor provides conversation history context
4. LLM generates response using both contexts
5. Exchange is added to history
6. Compression happens automatically when needed

## File Structure

```
project/
├── klepetalnik.py          # Main chatbot application
├── history_compressor.py   # Smart history compression logic
├── rag.py                  # RAG system implementation
├── update_rag.py           # Script to update RAG collections
├── config.py               # Configuration settings
├── auth.py                 # Authentication system
├── nastavitve.json         # Mode configurations
├── kode.json              # User credentials (create from sample)
└── kode.sample.json       # Sample user credentials
```

## Troubleshooting

### Common Issues

1. **Qdrant connection errors:**
   - Ensure Docker is running: `docker ps`
   - Verify Qdrant container is running: `docker run -p 6333:6333 qdrant/qdrant`

2. **Ollama connection errors:**
   - Ensure Ollama is running: `ollama serve`
   - Check models are downloaded: `ollama list`

3. **Authentication failures:**
   - Verify `kode.json` exists and is valid JSON
   - Check password codes match exactly

4. **RAG not working:**
   - Ensure collection exists: use `update_rag.py` to create it
   - Check documents are properly formatted in JSON array
   - Make sure Qdrant is running

### Debugging

- Check `debugx.log` for detailed conversation logs
- Monitor console output for error messages
- Verify all services are running on expected ports

## Customization

### Adding New Models

1. Pull the model with Ollama:
```bash
ollama pull your-model-name
```

2. Update `nastavitve.json` with model settings

### Creating Custom Prompts

Edit the prompt templates in `nastavitve.json` for different modes. The system prompt should include:
- Role definition
- Response guidelines
- Conversation context placeholder (`{conversation_context}`)

### Modifying Compression Settings

In `klepetalnik.py`, adjust the `SmartHistoryCompressor` parameters:
- `max_raw_history`: Number of recent exchanges to keep uncompressed
- `compression_threshold`: When to trigger compression
- `compression_batch_size`: How many exchanges to compress at once

## Authentication Setup

Create `kode.json` based on `kode.sample.json`:

```json
[
  {
    "name": "teacher",
    "code": "teacher123", 
    "mode": "pro1"
  },
  {
    "name": "student",
    "code": "student123",
    "mode": "generic"
  }
]
```

**Classroom Authentication Note**: This system uses simplified authentication designed for educational environments. The `kode.json` file contains password codes that can be used with any username. This allows you to distribute a single code to all students in a classroom while still tracking individual usernames for conversation history and metadata purposes.

- **Username**: Can be any identifier (student name, ID, etc.) - used for display and session tracking
- **Password**: Must match exactly one of the codes in `kode.json`
- **Mode**: Determines which configuration from `nastavitve.json` is applied

**Example Classroom Setup**:
```json
[
  {
    "name": "lecture1",
    "code": "python2024",
    "mode": "pro1"
  },
  {
    "name": "workshop", 
    "code": "coding123",
    "mode": "generic"
  }
]
```

Students would then login with:
- Username: Their actual name or identifier
- Password: "csharp2024" (for the programming lecture mode)

This approach can provide personalized conversation history per student while using shared authentication codes for classroom management.

## MIT License

Copyright (c) 2025 Klepetalnik

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Support

For issues and questions:
1. Check the debug logs in `debugx.log`
2. Verify all prerequisite services are running
3. Ensure models are properly downloaded with Ollama
