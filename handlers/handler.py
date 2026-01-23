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
    
    await progress_manager.update_progress(from_id, task_id, 10)
    audio_path = await f.save_audio(file_path)
    if not audio_path:
        data['error'] = "Oops! Couldn't get that one."
        await progress_manager.mark_error(from_id, task_id)
        return
    
    await progress_manager.update_progress(from_id, task_id, 30)
    transcription = await o.transcribe(audio_path)
    
    if not transcription:
        data['error'] = "Oops! Couldn't transcribe that one."
        await progress_manager.mark_error(from_id, task_id)
        await f.delete_audio(audio_path)
        return
    
    await progress_manager.update_progress(from_id, task_id, 60)
    data['transcription'] = transcription
    await nc.pub("correctrice.send.transcription", data)
    
    await progress_manager.update_progress(from_id, task_id, 75)
    correction = await g.correct_text(transcription)
    if not correction:
        data['error'] = "Oops! Couldn't correct that one."
        await progress_manager.mark_error(from_id, task_id)
        await f.delete_audio(audio_path)
        return
    
    await progress_manager.update_progress(from_id, task_id, 90)
    data['correction'] = correction
    await nc.pub("correctrice.send.correction", data)
    
    await progress_manager.update_progress(from_id, task_id, 100)
    await f.delete_audio(audio_path)
    
    await progress_manager.complete_task(from_id, task_id)

@nc.sub("correctrice.send.transcription")
async def handle_transcription(data={}):
    message_id = data.get("message_id")
    from_id = data.get("from_id")
    transcription = data.get("transcription")
    
    sent_message = await t.send_message(
        chat_id=from_id,
        text=transcription,
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
        chat_id = from_id,
        text = affirmation,
        reply_parameters = {
            "message_id": message_id
        }
    )
    if sent_message:
        await progress_manager.register_user_message(from_id, sent_message.get("message_id"))