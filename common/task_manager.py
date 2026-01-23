import logging
import asyncio
from datetime import datetime, timedelta
from services.telegram import TelegramBot as t

logger = logging.getLogger(__name__)

class TaskProgress:
    def __init__(self, task_id, message_id):
        self.task_id = task_id
        self.message_id = message_id
        self.progress = 0
        self.error = False
        self.error_time = None

class UserProgressTracker:
    def __init__(self, from_id):
        self.from_id = from_id
        self.progress_message_id = None
        self.tasks = {}
        self.last_user_message_id = 0
        self.send_lock = asyncio.Lock()  # Per-user lock for sending

class ProgressBarManager:
    def __init__(self):
        self.users = {}
        self._lock = asyncio.Lock()
    
    def _generate_progress_bar(self, progress, error=False):
        if error:
            return "░░░░░░░░░░░░░░░░░░░░ [ERROR]"
        
        total_blocks = 20
        filled_blocks = int((progress / 100) * total_blocks)
        empty_blocks = total_blocks - filled_blocks
        
        bar = "█" * filled_blocks + "░" * empty_blocks
        return f"{bar} [{progress}%]"
    
    def _generate_message(self, tracker):
        current_time = datetime.now()
        tasks_to_remove = []
        
        for task_id, task in tracker.tasks.items():
            if task.error and task.error_time:
                if current_time - task.error_time > timedelta(minutes=5):
                    tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del tracker.tasks[task_id]
        
        if not tracker.tasks:
            return None
        
        lines = [f"Tasks: {len(tracker.tasks)};", ""]
        
        for idx, (task_id, task) in enumerate(tracker.tasks.items(), 1):
            progress_bar = self._generate_progress_bar(task.progress, task.error)
            lines.append(f"{idx}- {progress_bar}")
        
        return "\n".join(lines)
    
    async def register_user_message(self, from_id, message_id):
        async with self._lock:
            if from_id not in self.users:
                self.users[from_id] = UserProgressTracker(from_id)
            
            tracker = self.users[from_id]
            
            if tracker.progress_message_id and message_id > tracker.progress_message_id:
                tracker.last_user_message_id = message_id
        
        # Call outside main lock to avoid blocking other users
        await self._send_progress(from_id)
    
    async def start_task(self, from_id, message_id, task_id=None):
        if task_id is None:
            task_id = f"task_{message_id}"
        
        async with self._lock:
            if from_id not in self.users:
                self.users[from_id] = UserProgressTracker(from_id)
            
            tracker = self.users[from_id]
            tracker.tasks[task_id] = TaskProgress(task_id, message_id)
            tracker.last_user_message_id = message_id
        
        await self._send_progress(from_id)
    
    async def update_progress(self, from_id, task_id, progress):
        async with self._lock:
            if from_id not in self.users or task_id not in self.users[from_id].tasks:
                return
            
            self.users[from_id].tasks[task_id].progress = progress
        
        await self._send_progress(from_id)
    
    async def mark_error(self, from_id, task_id):
        async with self._lock:
            if from_id not in self.users or task_id not in self.users[from_id].tasks:
                return
            
            task = self.users[from_id].tasks[task_id]
            task.error = True
            task.error_time = datetime.now()
            task.progress = 0
        
        await self._send_progress(from_id)
    
    async def complete_task(self, from_id, task_id):
        async with self._lock:
            if from_id not in self.users or task_id not in self.users[from_id].tasks:
                return
            
            del self.users[from_id].tasks[task_id]
        
        await self._send_progress(from_id)
    
    async def _send_progress(self, from_id):
        # Get tracker reference
        async with self._lock:
            if from_id not in self.users:
                return
            tracker = self.users[from_id]
        
        # Use per-user send lock to prevent concurrent sends for same user
        async with tracker.send_lock:
            # Re-generate message inside send lock to get latest state
            async with self._lock:
                message_text = self._generate_message(tracker)
                current_progress_msg_id = tracker.progress_message_id
            
            if message_text is None:
                if current_progress_msg_id:
                    r = await t.call(
                        "deleteMessage",
                        chat_id=from_id,
                        message_id=current_progress_msg_id
                    )
                    
                    async with self._lock:
                        tracker.progress_message_id = None
                return
            
            message_text = "<code>"+message_text+"</code>"
            
            if current_progress_msg_id:
                try:
                    result = await t.call(
                        "editMessageText",
                        chat_id=from_id,
                        message_id=current_progress_msg_id,
                        text=message_text,
                        parse_mode='HTML'
                    )
                    if not result:
                        # Delete old message before sending new one
                        r = await t.call(
                            "deleteMessage",
                            chat_id=from_id,
                            message_id=current_progress_msg_id
                        )
                        
                        sent_message = await t.send_message(
                            chat_id=from_id,
                            text=message_text,
                            parse_mode='HTML'
                        )
                        if sent_message:
                            async with self._lock:
                                tracker.progress_message_id = sent_message.get("message_id")
                except:
                    # Delete old message before sending new one
                    r = await t.call(
                        "deleteMessage",
                        chat_id=from_id,
                        message_id=current_progress_msg_id
                    )
                    
                    sent_message = await t.send_message(
                        chat_id=from_id,
                        text=message_text,
                        parse_mode='HTML'
                    )
                    if sent_message:
                        async with self._lock:
                            tracker.progress_message_id = sent_message.get("message_id")
            else:
                sent_message = await t.send_message(
                    chat_id=from_id,
                    text=message_text,
                    parse_mode='HTML'
                )
                if sent_message:
                    async with self._lock:
                        tracker.progress_message_id = sent_message.get("message_id")

progress_manager = ProgressBarManager()