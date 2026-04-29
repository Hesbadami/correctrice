import logging
import asyncio

from services.telegram import TelegramBot as t

logger = logging.getLogger(__name__)


class ProgressManager:
    def __init__(self):
        self._users: dict[int, dict] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _get_lock(self, from_id: int) -> asyncio.Lock:
        if from_id not in self._locks:
            self._locks[from_id] = asyncio.Lock()
        return self._locks[from_id]

    async def start_task(self, from_id, task_id):
        async with self._get_lock(from_id):
            if from_id not in self._users:
                self._users[from_id] = {"tasks": set(), "message_id": None, "last_text": None}

            user = self._users[from_id]
            user["tasks"].add(task_id)
            await self._update_message(from_id)

    async def complete_task(self, from_id, task_id):
        async with self._get_lock(from_id):
            if from_id not in self._users:
                return

            user = self._users[from_id]
            user["tasks"].discard(task_id)
            await self._update_message(from_id)

    async def mark_error(self, from_id, task_id):
        # Same as complete — remove from active set.
        # The error message itself is handled by the caller.
        await self.complete_task(from_id, task_id)

    async def _update_message(self, from_id):
        """Must be called while holding the user's lock."""
        user = self._users[from_id]
        count = len(user["tasks"])
        msg_id = user["message_id"]

        if count == 0:
            # All done — delete the status message
            if msg_id:
                try:
                    await t.call("deleteMessage", chat_id=from_id, message_id=msg_id)
                except Exception as e:
                    logger.debug(f"Failed to delete progress message: {e}")
                user["message_id"] = None
                user["last_text"] = None
            return

        text = f"⏳ Processing ({count} in queue)"

        # Skip if text hasn't changed — avoids Telegram 400 on identical edits
        if text == user["last_text"] and msg_id:
            return

        if msg_id:
            try:
                result = await t.call(
                    "editMessageText",
                    chat_id=from_id,
                    message_id=msg_id,
                    text=text,
                )
                if result:
                    user["last_text"] = text
                    return
            except Exception as e:
                logger.debug(f"Failed to edit progress message: {e}")

        # Either no existing message or edit failed — send a new one
        try:
            sent = await t.send_message(chat_id=from_id, text=text)
            if sent:
                user["message_id"] = sent.get("message_id")
                user["last_text"] = text
        except Exception as e:
            logger.warning(f"Failed to send progress message to {from_id}: {e}")


progress_manager = ProgressManager()