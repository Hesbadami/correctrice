import logging
import os

from common.nats_server import nc
from common.task_manager import progress_manager
from services.telegram import TelegramBot as t
from services.openai_manager import openai_manager as o
from services.ffmpeg_manager import FFmpegManager as f
from services.gemini import gemini_manager as g

logger = logging.getLogger(__name__)


@nc.sub("correctrice.file_received")
async def handle_file(data={}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")
    file_path = data.get("file_path")

    task_id = f"task_{message_id}"

    await progress_manager.register_user_message(from_id, message_id)
    await progress_manager.start_task(from_id, message_id, task_id)

    # --- 1. Download -------------------------------------------------------
    await progress_manager.update_progress(from_id, task_id, 10)
    audio_path = await f.save_audio(file_path)
    if not audio_path:
        await progress_manager.mark_error(from_id, task_id)
        return

    # --- 2. Transcribe (hold the result, do not publish yet) ---------------
    await progress_manager.update_progress(from_id, task_id, 30)
    transcription = await o.transcribe(audio_path)
    if not transcription:
        await progress_manager.mark_error(from_id, task_id)
        await _safe_delete(audio_path)
        return

    # --- 3. Correct --------------------------------------------------------
    await progress_manager.update_progress(from_id, task_id, 70)
    correction = await g.correct_text(transcription)

    # --- 4. Deliver as a pair (back-to-back publishes) ---------------------
    await progress_manager.update_progress(from_id, task_id, 90)

    data['transcription'] = transcription

    if correction:
        data['correction'] = correction
        # Both publishes fire in sequence. The subscriber processes them in
        # order, so the two Telegram messages land adjacent in the chat.
        await nc.pub("correctrice.send.transcription", data)
        await nc.pub("correctrice.send.correction", data)
    else:
        # Graceful degradation: transcription still has value on its own.
        data['transcription_only'] = True
        await nc.pub("correctrice.send.transcription", data)
        logger.warning(f"Correction failed for task {task_id}, sent transcription only")

    await progress_manager.update_progress(from_id, task_id, 100)
    await _safe_delete(audio_path)
    await progress_manager.complete_task(from_id, task_id)


async def _safe_delete(audio_path):
    try:
        await f.delete_audio(audio_path)
    except Exception as e:
        logger.warning(f"Failed to delete audio {audio_path}: {e}")


@nc.sub("correctrice.send.transcription")
async def handle_transcription(data={}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")
    transcription = data.get("transcription")
    transcription_only = data.get("transcription_only", False)

    text = transcription
    if transcription_only:
        text = f"{transcription}\n\n⚠️ Correction unavailable — transcription only."

    sent_message = await t.send_message(
        chat_id=from_id,
        text=text,
        reply_parameters={"message_id": message_id}
    )
    if sent_message:
        await progress_manager.register_user_message(from_id, sent_message.get("message_id"))


@nc.sub("correctrice.send.correction")
async def handle_correction(data={}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")
    correction = data.get("correction")

    sent_message = await t.send_message(
        chat_id=from_id,
        text=correction,
        reply_parameters={"message_id": message_id}
    )
    if sent_message:
        await progress_manager.register_user_message(from_id, sent_message.get("message_id"))


@nc.sub("correctrice.send.affirmation")
async def handle_affirmation(data: dict = {}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")
    affirmation = await o.affirmation()

    sent_message = await t.send_message(
        chat_id=from_id,
        text=affirmation,
        reply_parameters={"message_id": message_id}
    )
    if sent_message:
        await progress_manager.register_user_message(from_id, sent_message.get("message_id"))


@nc.sub("correctrice.send.expiry_notice")
async def handle_expiry_notice(data: dict = {}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")

    text = (
        "⏳ Your access has expired.\n\n"
        "Please renew to keep using the bot. "
        "Contact the admin to extend your subscription."
    )

    sent_message = await t.send_message(
        chat_id=from_id,
        text=text,
        reply_parameters={"message_id": message_id},
    )
    if sent_message:
        await progress_manager.register_user_message(from_id, sent_message.get("message_id"))