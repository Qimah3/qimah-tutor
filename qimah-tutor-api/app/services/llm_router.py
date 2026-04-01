import os
from abc import ABC, abstractmethod


class LLMRouter(ABC):
    """Provider-agnostic LLM interface."""

    def __init__(self, config: dict):
        self.model = config.get("model", "gpt-4o-mini")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4000)
        self.timeout = config.get("timeout", 30)

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Send messages to the LLM and return the response text."""


class OpenAIRouter(LLMRouter):
    """Routes requests to OpenAI API."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None  # lazy init to avoid failing when no API key at construction time

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                timeout=self.timeout,
            )
        return self._client

    async def complete(self, messages: list[dict], **kwargs) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("OpenAI returned an empty response")
        return content


class ClaudeRouter(LLMRouter):
    """Routes requests to Anthropic Claude API."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._client = None  # lazy init to avoid failing when no API key at construction time

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.AsyncAnthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY"),
                timeout=self.timeout,
            )
        return self._client

    async def complete(self, messages: list[dict], **kwargs) -> str:
        # Anthropic separates system prompt from human/assistant turns
        client = self._get_client()
        system = ""
        filtered = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                filtered.append(msg)

        response = await client.messages.create(
            model=self.model,
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            temperature=kwargs.get("temperature", self.temperature),
            system=system if system else "",
            messages=filtered,
        )
        if not response.content:
            raise RuntimeError("Claude returned an empty response")
        return response.content[0].text


def get_router(config: dict) -> LLMRouter:
    """Factory: return the correct LLMRouter for the given provider config."""
    provider = config.get("provider", "openai")
    if provider == "openai":
        return OpenAIRouter(config)
    elif provider == "claude":
        return ClaudeRouter(config)
    else:
        raise ValueError(f"unsupported LLM provider: '{provider}'. Choose 'openai' or 'claude'.")
