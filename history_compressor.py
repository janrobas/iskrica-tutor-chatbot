import time
from typing import List, Dict, Tuple
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import asyncio

class SmartHistoryCompressor:
    def __init__(self,
                 compression_model,
                 max_raw_history: int = 6,
                 compression_threshold: int = 3,
                 compression_batch_size: int = 3
                 ):
        """
        Args:
            compression_model: The LLM model to use for compression
            max_raw_history: How many recent Q/A pairs to keep uncompressed
            compression_threshold: How many old exchanges to accumulate before compressing
            compression_batch_size: How many exchanges to compress at once
        """
        self.max_raw_history = max_raw_history
        self.compression_threshold = compression_threshold
        self.compression_batch_size = compression_batch_size
        
        self.raw_history = []  # Recent uncompressed exchanges
        self.compressed_history = ""  # Single compressed summary that gets updated
        self.compression_model = compression_model
        
    async def add_exchange(self, question: str, answer: str) -> None:
        """Add a new Q/A exchange"""
        # Add to raw history (most recent)
        self.raw_history.append({
            "question": question,
            "answer": answer,
            "timestamp": time.time(),
            "pending": False,
            "compressing": False
        })
        
        # Maintain raw history size - mark exceeding entries as pending but don't delete them
        if len(self.raw_history) > self.max_raw_history:
            # Calculate how many entries exceed the max
            excess_count = len(self.raw_history) - self.max_raw_history
            
            # Mark the oldest excess entries as pending (but keep them in raw_history)
            for i in range(excess_count):
                if not self.raw_history[i]['compressing']:  # Only mark if not already compressing
                    self.raw_history[i]['pending'] = True
        
        # Check if we should compress pending exchanges
        await self._check_compression()
    
    async def _check_compression(self) -> None:
        """Compress pending exchanges if threshold is reached"""
        # Count how many entries are pending but not currently being compressed
        pending_count = len([ex for ex in self.raw_history if ex['pending'] and not ex['compressing']])
        
        if pending_count >= self.compression_threshold:
            # Get all entries that are pending but not currently compressing
            pending_exchanges = [ex for ex in self.raw_history if ex['pending'] and not ex['compressing']]
            
            # Mark these entries as compressing to avoid double-processing
            for ex in pending_exchanges:
                ex['compressing'] = True
            
            try:
                # Create new compressed summary by combining current compressed history with pending exchanges
                new_compressed_summary = await self._create_compressed_summary(pending_exchanges)
                self.compressed_history = new_compressed_summary
                
                # Now remove the compressed entries from raw_history
                self.raw_history = [ex for ex in self.raw_history if not ex['compressing']]
                
                # Reset pending flags for remaining entries if needed
                for ex in self.raw_history:
                    ex['pending'] = False
                
                # Re-mark excess entries as pending if we're still over limit
                if len(self.raw_history) > self.max_raw_history:
                    excess_count = len(self.raw_history) - self.max_raw_history
                    for i in range(excess_count):
                        self.raw_history[i]['pending'] = True
                        
            except Exception as e:
                # If compression fails, just clear the compressing entries and move on
                print(f"Compression failed: {e}, clearing pending history")
                self.raw_history = [ex for ex in self.raw_history if not ex['compressing']]

    async def _create_compressed_summary(self, exchanges: List[Dict]) -> str:
        """Use LLM to create intelligent summary of exchanges, including previous compressed history"""
        if not exchanges:
            return self.compressed_history  # Return existing summary if no new exchanges
        
        # Prepare the conversation context from exchanges
        conversation_text = ""
        for i, ex in enumerate(exchanges):
            conversation_text += f"Question {i+1}: {ex['question']}\n"
            conversation_text += f"Answer {i+1}: {ex['answer'][:200]}{'...' if len(ex['answer']) > 200 else ''}\n\n"
        
        # Create prompt that includes previous compressed history for context
        if self.compressed_history:
            prompt = f"""
            Previous conversation summary: {self.compressed_history}
            
            New exchanges to incorporate:
            {conversation_text}
            
            Create a new comprehensive summary that:
            1. Preserves the key information from the previous summary
            2. Incorporates the new exchanges
            3. Maintains continuity and context
            4. Is concise but informative (2-3 sentences)
            
            Updated summary:
            """
        else:
            prompt = f"""
            Create a concise summary (2-3 sentences) of these exchanges:
            
            {conversation_text}
            
            Focus on the main topics, questions, and key information discussed.
            
            Summary:
            """
        
        # Use async call to the compression model
        summary_response = await self.compression_model.ainvoke(prompt)
        return summary_response.strip()
    
    def get_conversation_context(self) -> str:
        """Get the full conversation context for system prompt"""
        context_parts = []
        
        # Add compressed history if it exists
        if self.compressed_history:
            context_parts.append(f"[Previous Summary] {self.compressed_history}")
        
        # Add info about pending exchanges if any
        pending_count = len([ex for ex in self.raw_history if ex['pending']])
        if pending_count > 0:
            context_parts.append(f"[Recent] {pending_count} exchanges pending compression")
        
        return "\n".join(context_parts) if context_parts else "No previous conversation."
    
    def get_message_history(self) -> List[BaseMessage]:
        """Get recent message history for MessagesPlaceholder - includes all non-pending raw history"""
        messages = []
        
        # Only include non-pending exchanges in message history
        # This ensures we don't include exchanges that are about to be compressed
        for exchange in self.raw_history:
            if not exchange['pending'] and not exchange['compressing']:
                messages.append(HumanMessage(content=exchange["question"]))
                messages.append(AIMessage(content=exchange["answer"]))
        
        return messages
    
    def get_stats(self) -> Dict:
        """Get compression statistics for debugging"""
        pending_count = len([ex for ex in self.raw_history if ex['pending']])
        compressing_count = len([ex for ex in self.raw_history if ex['compressing']])
        active_count = len([ex for ex in self.raw_history if not ex['pending'] and not ex['compressing']])
        
        return {
            "raw_exchanges_total": len(self.raw_history),
            "raw_exchanges_active": active_count,
            "pending_compression": pending_count,
            "currently_compressing": compressing_count,
            "compressed_summary_exists": bool(self.compressed_history),
            "compressed_summary_length": len(self.compressed_history) if self.compressed_history else 0
        }
    