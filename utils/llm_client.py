"""
Centralized LLM Client — Single Point of Configuration

Abstracts LLM calls across the project using LangChain.
Supports both local Ollama and cloud providers seamlessly.

Usage:
    from utils import get_llm_client
    
    client = get_llm_client()
    response = client.chat(
        messages=[{"role": "user", "content": "What is Python?"}],
        temperature=0.7,
        max_tokens=512
    )
    print(response)
"""

from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from utils.config import get_config
from utils.logging import get_logger

load_dotenv()
logger = get_logger(__name__)


class LLMClient:
    """Unified LLM client using LangChain."""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize LLM client.

        Args:
            model: Model name (default: from config)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum response tokens
            base_url: API endpoint (default: from config)
            api_key: API key (default: from config)
        """
        config = get_config()
        
        self.model = model or config.ollama_model
        self.temperature = temperature if temperature is not None else config.llm_temperature
        self.max_tokens = max_tokens or config.llm_max_tokens
        self.base_url = base_url or config.ollama_base_url
        self.api_key = api_key or config.openai_api_key

        logger.debug(f"Initializing LLMClient: model={self.model}, temp={self.temperature}")

        # Initialize LangChain ChatOpenAI
        self._client = ChatOpenAI(
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

    def chat(
        self,
        messages: list[dict],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Send chat messages and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system message to prepend
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Response text string
        """
        # Override parameters if provided
        if temperature is not None or max_tokens is not None:
            client = ChatOpenAI(
                model=self.model,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
        else:
            client = self._client

        # Build message list
        langchain_messages = []

        if system_prompt:
            langchain_messages.append(SystemMessage(content=system_prompt))

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if not role or not content:
                continue

            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "user":
                langchain_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))

        # Call LLM
        response = client.invoke(langchain_messages)
        return response.content

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text from a simple prompt (no conversation history).

        Args:
            prompt: Text prompt
            system_prompt: Optional system message
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Response text string
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def get_chat_model(self) -> ChatOpenAI:
        """
        Get the underlying LangChain ChatOpenAI model directly.
        
        Useful for LangChain chains and LCEL pipes:
            from utils import get_llm_client
            llm = get_llm_client().get_chat_model()
            chain = prompt | llm
        
        Returns:
            ChatOpenAI instance (Runnable)
        """
        return self._client


# Singleton instance
_client_instance: Optional[LLMClient] = None


def get_llm_client(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
) -> LLMClient:
    """
    Get or create the global LLM client instance.

    Args:
        model: Model name
        temperature: Sampling temperature
        max_tokens: Maximum response tokens

    Returns:
        LLMClient instance
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = LLMClient(
            model=model, temperature=temperature, max_tokens=max_tokens
        )

    return _client_instance


def reset_llm_client():
    """Reset the global client instance (useful for testing)."""
    global _client_instance
    _client_instance = None



