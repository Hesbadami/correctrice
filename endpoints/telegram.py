import logging
from typing import Optional
import json
from datetime import datetime
import time
import os

from common.fastapi_server import api
from common.mysql import MySQL as db
from common.nats_server import nc
from common.config import (
    TELEGRAM_SECRET, TELEGRAM_WHITELIST,
    DOCKER_VIDEO_MOUNTPOINT, DOCKER_AUDIO_MOUNTPOINT, DOCKER_VIDEONOTE_MOUNTPOINT, DOCKER_VOICE_MOUNTPOINT
)

from services.telegram import TelegramBot as t

from fastapi import Request, Header, HTTPException

logger = logging.getLogger("telegram")

async def get_video_path(file_id):
    docker_path = await t.get_file(file_id)
    head_tail = os.path.split(docker_path)
    return DOCKER_VIDEO_MOUNTPOINT + head_tail[1]
async def get_audio_path(file_id):
    docker_path = await t.get_file(file_id)
    head_tail = os.path.split(docker_path)
    return DOCKER_AUDIO_MOUNTPOINT + head_tail[1]
async def get_video_note_path(file_id):
    docker_path = await t.get_file(file_id)
    head_tail = os.path.split(docker_path)
    return DOCKER_VIDEONOTE_MOUNTPOINT + head_tail[1]
async def get_voice_path(file_id):
    docker_path = await t.get_file(file_id)
    head_tail = os.path.split(docker_path)
    return DOCKER_VOICE_MOUNTPOINT + head_tail[1]

@api.post("/webhook/telegram")
@api.post("/webhook/telegram/")
async def telegram_webhook(
    request: Request = None
):

    try:
        body = await request.body()

        try:
            update_data = json.loads(body.decode('utf-8'))
            message = update_data.get("message", {})
            message_id = message.get("message_id")
            from_id = message.get("from", {}).get("id")
            
            if int(from_id) not in TELEGRAM_WHITELIST:
                return {"status": "ok"}
            
            data = {
                'message_id': message_id,
                'from_id': from_id
            }
            
            if 'video' in message:
                video = message.get('video')
                file_path = await get_video_path(video['file_id'])
            elif 'voice' in message:
                voice = message.get('voice')
                file_path = await get_voice_path(voice['file_id'])
            elif 'audio' in message:
                audio = message.get('audio')
                file_path = await get_audio_path(audio['file_id'])
            elif 'video_note' in message:
                video_note = message.get('video_note')
                file_path = await get_video_note_path(video_note['file_id'])
            else:

                await nc.pub(
                    "correctrice.send.affirmation",
                    data
                )
                return {"status": "ok"}
            
            data |= {
                'file_path': file_path
            }
            
            await nc.pub(
                "correctrice.file_received", data
            )
            
            logger.info(f"Received update:\n{json.dumps(update_data, indent=4)[:50]}...")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        return {"status": "ok"}
        
    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error processing telegram webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")