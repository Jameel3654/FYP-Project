"""
LLM calling module supporting GPT-4 and Gemini.
"""
from typing import Dict, Any
import os
import openai
import google.generativeai as genai
from ..config import settings

class LLMCaller:
    """
    Class for executing QA prompts with different LLM providers.
    """
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
    def call(self, prompt: str, context: str, question: str, provider: str = 'gpt-4') -> Dict[str, Any]:
        """
        Calls the specified LLM provider to answer the question based on the context.
        Returns the answer, tokens used, and provider name.
        """
        system_prompt = "You are a helpful document QA assistant. Answer the user's question based ONLY on the provided context."
        full_prompt = f"Context:\n{context}\n\nQuestion:\n{question}\n{prompt}"
        
        provider_lower = provider.lower()
        
        if provider_lower == 'gpt-4':
            try:
                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": full_prompt}
                    ],
                    temperature=0.0
                )
                
                answer = response.choices[0].message.content
                tokens_used = response.usage.total_tokens
                
                return {
                    "answer": answer,
                    "tokens_used": tokens_used,
                    "provider": "gpt-4"
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "provider": "gpt-4"
                }
                
        elif provider_lower == 'gemini':
            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                
                # Combine system prompt with full prompt for Gemini
                gemini_prompt = f"{system_prompt}\n\n{full_prompt}"
                
                response = model.generate_content(gemini_prompt)
                
                tokens_used = len(gemini_prompt) // 4 + len(response.text) // 4
                
                return {
                    "answer": response.text,
                    "tokens_used": tokens_used,
                    "provider": "gemini"
                }
            except Exception as e:
                return {
                    "error": str(e),
                    "provider": "gemini"
                }
                
        else:
            return {
                "error": f"Unsupported provider: {provider}",
                "provider": provider
            }
