from google import genai
from google.genai import types
from common.config import GEMINI_API_KEY
import logging
import anyio
from asynciolimiter import StrictLimiter

logger = logging.getLogger(__name__)

class GeminiManager:
    
    _rate_limiter = StrictLimiter(15/60)  # 15 requests per minute (Gemini free tier)

    def __init__(self, logger: logging.Logger):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.logger = logger
        self.max_retries = 3
        self.system_instruction = (
            "Please correct this text for me (A1 english level)\n\n"
            "Only focus on core english, Don't correct punctuation, capitalization or typo errors.\n\n"
            "Return corrections in pairs like\n"
            "❌ Incorrect version\n"
            "✅ Corrected"
        )
    
    async def correct_text(self, text: str) -> str | None:
        await self._rate_limiter.wait()
        
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.info(f"Correction attempt {attempt}/{self.max_retries}")
                
                # Run blocking API call in thread pool
                response = await anyio.to_thread.run_sync(
                    self._generate_content, text
                )
                
                self.logger.info("Text correction successful")
                return response.text
                
            except Exception as e:
                self.logger.warning(
                    f"Error on attempt {attempt}/{self.max_retries}: {e}"
                )
                
                if attempt < self.max_retries:
                    await anyio.sleep(2 * attempt)  # Exponential backoff
                else:
                    self.logger.error("Max retries reached")
                    return None
        
        return None
    
    def _generate_content(self, text: str):
        """Helper method to call Gemini API synchronously (runs in thread pool)"""
        return self.client.models.generate_content(
            model="gemini-2.0-flash-exp",
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                temperature=0.3
            ),
            contents=text
        )


gemini_manager = GeminiManager(logger)