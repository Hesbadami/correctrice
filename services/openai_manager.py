
from uuid import uuid4
from common.config import OPENAI_TOKEN, OPENAI_MODEL
import tiktoken
import logging
import anyio
from openai import AsyncOpenAI
from openai import APIError, RateLimitError, APIConnectionError, APITimeoutError

from asynciolimiter import StrictLimiter


logger = logging.getLogger(__name__)


class OpenAIManager:
    
    _rate_limiter = StrictLimiter(60/1)

    def __init__(self, logger: logging.Logger):
        self.openai_client = AsyncOpenAI(
            api_key=OPENAI_TOKEN
        )
        self.logger = logger
        self.max_retries = 3

    
    async def transcribe(self, input_file):
        await self._rate_limiter.wait()
        
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(f"Transcription attempt {attempt}/{self.max_retries} for file: {input_file}")
                
                # Read file in thread pool to avoid blocking
                file_content = await anyio.to_thread.run_sync(self._read_file, input_file)
                
                # OpenAI client is async, so we can await directly
                transcription = await self.openai_client.audio.transcriptions.create(
                    model="whisper-1",  # This is the only Whisper model available
                    temperature=0.1,
                    language='en',
                    file=("audio.wav", file_content, "audio/wav")
                )
                
                self.logger.info(f"Transcription successful for file: {input_file}")
                return transcription.text
                
            except RateLimitError as e:
                # Extract retry-after header if available
                retry_after = getattr(e, 'retry_after', None) or 60
                self.logger.warning(
                    f"Rate limit hit on attempt {attempt}/{self.max_retries}. "
                    f"Waiting {retry_after} seconds before retry. Error: {e}"
                )
                
                if attempt < self.max_retries:
                    await anyio.sleep(retry_after)
                else:
                    self.logger.error(f"Max retries reached due to rate limiting for file: {input_file}")
                    return None
                    
            except APITimeoutError as e:
                self.logger.warning(
                    f"Timeout on attempt {attempt}/{self.max_retries}. Error: {e}"
                )
                
                if attempt < self.max_retries:
                    await anyio.sleep(5 * attempt)  # Exponential backoff
                else:
                    self.logger.error(f"Max retries reached due to timeouts for file: {input_file}")
                    return None
                    
            except APIConnectionError as e:
                self.logger.warning(
                    f"Connection error on attempt {attempt}/{self.max_retries}. Error: {e}"
                )
                
                if attempt < self.max_retries:
                    await anyio.sleep(3 * attempt)  # Exponential backoff
                else:
                    self.logger.error(f"Max retries reached due to connection errors for file: {input_file}")
                    return None
                    
            except APIError as e:
                # Generic API error (400, 500, etc.)
                self.logger.warning(
                    f"API error on attempt {attempt}/{self.max_retries}. "
                    f"Status: {getattr(e, 'status_code', 'unknown')}. Error: {e}"
                )
                
                # Don't retry on 4xx errors (except rate limit which is handled above)
                if hasattr(e, 'status_code') and 400 <= e.status_code < 500:
                    self.logger.error(f"Client error (4xx), not retrying for file: {input_file}")
                    return None
                
                if attempt < self.max_retries:
                    await anyio.sleep(2 * attempt)
                else:
                    self.logger.error(f"Max retries reached due to API errors for file: {input_file}")
                    return None
                    
            except Exception as e:
                # Catch-all for unexpected errors
                self.logger.error(
                    f"Unexpected error on attempt {attempt}/{self.max_retries} for file {input_file}: {e}",
                    exc_info=True
                )
                
                if attempt < self.max_retries:
                    await anyio.sleep(2 * attempt)
                else:
                    self.logger.error(f"Max retries reached due to unexpected errors for file: {input_file}")
                    return None
        
        return None
    
    def _read_file(self, file_path):
        """Helper method to read file synchronously (runs in thread pool)"""
        with open(file_path, "rb") as f:
            return f.read()
        
    async def affirmation(self):
        
        await self._rate_limiter.wait()

        default_affirmation = "You're amazing! Keep shining! ✨💕"

        try:
            self.logger.info("Generating affirmation")
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Cheapest and fastest model
                messages=[
                    {
                        "role": "system",
                        "content": """You are Correctrice, a Transformer Autobot designed for English clarity and understanding. 
            You are calm, precise, and approachable, with a cyberpunk-futuristic feminine vibe. 
            You correct meaning, not style, spelling, or punctuation, and you always prioritize clear communication. 
            Your tone is concise, elegant, soft, and encouraging without being cheesy. 
            Keep it short (10-15 words), punchy, and grounded, like a friendly guide rather than a hustler. 
            Use subtle positive reinforcement, but do not lecture."""
                    },
                    {
                        "role": "user",
                        "content": "Give me an encouraging affirmation for someone who just failed at something."
                    }
                ],
                max_tokens=40,
                temperature=1.2
            )

            affirmation_text = response.choices[0].message.content.strip()
            self.logger.info(f"Affirmation generated: {affirmation_text}")
            return affirmation_text
            
        except RateLimitError as e:
            self.logger.warning(f"Rate limit hit while generating affirmation: {e}")
            return default_affirmation
            
        except (APITimeoutError, APIConnectionError) as e:
            self.logger.warning(f"Connection issue while generating affirmation: {e}")
            return default_affirmation
            
        except APIError as e:
            self.logger.warning(f"API error while generating affirmation: {e}")
            return default_affirmation
            
        except Exception as e:
            self.logger.error(f"Unexpected error while generating affirmation: {e}", exc_info=True)
            return default_affirmation
        
openai_manager = OpenAIManager(logger)