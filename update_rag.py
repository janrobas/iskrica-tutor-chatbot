import sys
import json
import argparse
from pathlib import Path
from config import Config
from rag import RAG

def main():
    parser = argparse.ArgumentParser(description='Update RAG collection with texts from JSON file')
    parser.add_argument('filename', help='Path to JSON file containing array of texts')
    parser.add_argument('collection_name', help='Name of the collection to update')
    
    args = parser.parse_args()
    
    # Validate file exists
    file_path = Path(args.filename)
    if not file_path.exists():
        print(f"Error: File '{args.filename}' not found!")
        sys.exit(1)
    
    # Load JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            texts = json.load(f)
        
        # Validate
        if not isinstance(texts, list):
            print("Error: JSON file should contain an array of texts!")
            sys.exit(1)
            
        if not all(isinstance(text, str) for text in texts):
            print("Error: All elements in the array must be strings!")
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format in file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)
    
    try:
        rag = RAG(
            qdrant_url=Config.QDRANT_URL, 
            embedding_model=Config.EMBEDDING_MODEL, 
            llama_model=Config.DEFAULT_LLAMA_MODEL
        )
        
        print(f"Adding {len(texts)} documents to collection '{args.collection_name}'...")
        
        rag.dodaj(text_array=texts, collection_name=args.collection_name, force_recreate = True)
        
        print(f"Successfully updated collection '{args.collection_name}' with {len(texts)} documents!")
        
            
    except Exception as e:
        print(f"Error updating RAG collection: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
