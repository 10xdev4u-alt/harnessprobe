from __future__ import annotations

import logging

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


def ask_model(client: OpenAI, prompt: str) -> str:
    logger.info("asking model")
    response = client.chat.completions.create(
        model="gpt",
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.choices:
        return ""
    logger.debug("received choices")
    return response.choices[0].message.content


def plain_helper(value: int) -> int:
    result = value * 2
    print(result)
    return value
