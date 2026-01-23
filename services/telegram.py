import logging
from urllib.parse import quote
from typing import Optional, Dict, Any, Union
import json

from common.config import TELEGRAM_TOKEN

import anyio
from anyio import to_thread, Semaphore
import httpx
from asynciolimiter import StrictLimiter

logger = logging.getLogger("telegram")

class TelegramBot:

    api_url = f"http://127.0.0.1:8081/bot{TELEGRAM_TOKEN}/"
    _rate_limiter = StrictLimiter(30/1)
    _message_rate_limiter = StrictLimiter(1)
    
    @classmethod
    async def call(cls, method: str, files: Optional[Dict] = None, **kwargs) -> Optional[Any]:
        
        await cls._rate_limiter.wait()

        url = f"{cls.api_url}{method}"
        logger.info(f"Making API call to {url} with parameters: {kwargs}")
        
        async with httpx.AsyncClient() as client:
            try:
                data = {}
                for key, value in kwargs.items():
                    if isinstance(value, (list, dict)):
                        data[key] = json.dumps(value)
                    else:
                        data[key] = value
                
                if files:
                    response = await client.post(url, data=data, files=files)
                else:
                    response = await client.post(url, data=data)
                    
                if response.status_code == 200:
                    response_data = response.json()
                    if not response_data.get('ok'):
                        logger.warning(f"API call to {url} failed with error: {response_data.get('description')}")
                        return None
                    
                    logger.info(f"API call to {url} succeeded")
                    return response_data.get('result')
                else:
                    logger.error(f"API call to {url} failed with status code {response.status_code} and response: {response.text}")
                    return None
                    
            except httpx.RequestError as e:
                logger.exception(f"An error occurred while making API call to {url}: {e}")
                return None

    @classmethod
    async def send_message(cls, chat_id: Union[int, str], text: str, **kwargs) -> Optional[Any]:
        if not chat_id or not text:
            logger.error("Chat ID and text are required to send a message.")
            return None
        
        TELEGRAM_MAX_LENGTH = 4096
        
        # If text fits in one message, send normally
        if len(text) <= TELEGRAM_MAX_LENGTH:
            await cls._message_rate_limiter.wait()
            return await cls.call('sendMessage', chat_id=chat_id, text=text, **kwargs)
        
        # Split long messages
        logger.info(f"Message exceeds {TELEGRAM_MAX_LENGTH} characters ({len(text)}), splitting into chunks")
        
        chunks = []
        remaining_text = text
        
        while remaining_text:
            if len(remaining_text) <= TELEGRAM_MAX_LENGTH:
                chunks.append(remaining_text)
                break
            
            # Find a good split point (prefer newline, then space)
            split_index = remaining_text.rfind('\n', 0, TELEGRAM_MAX_LENGTH)
            if split_index == -1 or split_index < TELEGRAM_MAX_LENGTH * 0.8:  # Don't split too early
                split_index = remaining_text.rfind(' ', 0, TELEGRAM_MAX_LENGTH)
            if split_index == -1:
                split_index = TELEGRAM_MAX_LENGTH
            
            chunks.append(remaining_text[:split_index])
            remaining_text = remaining_text[split_index:].lstrip()
        
        logger.info(f"Split message into {len(chunks)} chunks")
        
        # Send chunks sequentially
        results = []
        reply_parameters = kwargs.pop('reply_parameters', None)
        
        for i, chunk in enumerate(chunks):
            await cls._message_rate_limiter.wait()
            
            # Only include reply_parameters on the first chunk
            chunk_kwargs = kwargs.copy()
            if i == 0 and reply_parameters:
                chunk_kwargs['reply_parameters'] = reply_parameters
            
            result = await cls.call('sendMessage', chat_id=chat_id, text=chunk, **chunk_kwargs)
            results.append(result)
        
        # Return the last result (or all results if you prefer)
        return results[-1] if results else None
    
    @classmethod
    async def get_file(cls, file_id):
        response = await cls.call("getFile", file_id=file_id)
        path = response.get("file_path")
        return path