import logging
from typing import Optional
import json
import os

from common.fastapi_server import api
from common.mysql import MySQL as db
from common.nats_server import nc
from common.config import (
    TELEGRAM_SECRET,
    DOCKER_VIDEO_MOUNTPOINT, DOCKER_AUDIO_MOUNTPOINT,
    DOCKER_VIDEONOTE_MOUNTPOINT, DOCKER_VOICE_MOUNTPOINT,
)

from services.telegram import TelegramBot as t

from fastapi import Request, HTTPException

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
async def telegram_webhook(request: Request = None):
    try:
        body = await request.body()

        try:
            update_data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON")

        message = update_data.get("message", {})
        message_id = message.get("message_id")
        from_id = message.get("from", {}).get("id")

        if not from_id:
            return {"status": "ok"}

        # --- Access gate ---------------------------------------------------
        rows = await db.aexecute_query(
            """
            SELECT
                id,
                expiry_date,
                (expiry_date >= CURDATE())
                    AS is_active,
                (last_expiry_notice IS NULL OR last_expiry_notice < CURDATE())
                    AS notice_due
            FROM `user`
            WHERE
                user_id = %s
            LIMIT 1;
            """,
            (str(from_id),),
        )

        # Unknown user → silent. No response, no log noise. DDoS-proof.
        if not rows:
            return {"status": "ok"}

        user = rows[0]

        # Known but expired → throttled "please renew" notice, then drop.
        if not user["is_active"]:
            if user["notice_due"]:
                await db.aexecute_update(
                    """
                    UPDATE `user`
                    SET
                        last_expiry_notice = CURDATE()
                    WHERE
                        id = %s;
                    """,
                    (user["id"],),
                )
                await nc.pub(
                    "correctrice.send.expiry_notice",
                    {"message_id": message_id, "from_id": from_id},
                )
            return {"status": "ok"}

        # --- Active user: existing pipeline --------------------------------
        data = {"message_id": message_id, "from_id": from_id}

        if 'video' in message:
            file_path = await get_video_path(message['video']['file_id'])
        elif 'voice' in message:
            file_path = await get_voice_path(message['voice']['file_id'])
        elif 'audio' in message:
            file_path = await get_audio_path(message['audio']['file_id'])
        elif 'video_note' in message:
            file_path = await get_video_note_path(message['video_note']['file_id'])
        else:
            await nc.pub("correctrice.send.affirmation", data)
            return {"status": "ok"}

        data["file_path"] = file_path
        await nc.pub("correctrice.file_received", data)

        logger.info(f"Received update:\n{json.dumps(update_data, indent=4)[:50]}...")
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing telegram webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")