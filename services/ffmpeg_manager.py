from uuid import uuid4
from common.config import OPENAI_TOKEN, OPENAI_MODEL
import tiktoken
import logging
import ffmpeg
import subprocess
import os

from anyio import to_thread, Semaphore

logger = logging.getLogger(__name__)

class FFmpegManager:
    
    _audio_path = 'audios/'
    _semaphore = Semaphore(3)
    
    @classmethod
    async def save_audio(cls, input_path):
        
        file_name = os.path.split(input_path)[1]
        output_path = cls._audio_path + file_name + '.wav'

        async with cls._semaphore:
            logger.info(f"Starting audio conversion")
            
            process = (
                ffmpeg
                .input(input_path)
                .output(output_path, format='wav', acodec='pcm_s16le', ac=1, ar='16k')
                .overwrite_output()
                .compile()
            )
            
            # Prepend 'nice' to the FFmpeg command
            nice_command = ['nice', '-n', '10'] + process

            # Execute the FFmpeg command with 'nice'
            result = await to_thread.run_sync(
                subprocess.run,
                nice_command
            )
            if result.returncode != 0:
                return
            
            logger.info(f"Completed audio conversion")
            
        return output_path
    

    @classmethod
    async def delete_audio(cls, output_path):
        
        await to_thread.run_sync(
            os.remove,
            output_path
        )
        
        return output_path