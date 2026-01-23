import json
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from common.config import NATS_CFG

import nats
import anyio
from anyio.abc import TaskGroup
from anyio import Event

logger = logging.getLogger("nats")

class NATSServer:
    def __init__(self):
        self._connection : Optional[nats.NATS] = None
        self.pending_subscribers: List[tuple] = []
        self.pending_responders: List[tuple] = []
        self._task_group: Optional[TaskGroup] = None
        self._shutdown_event: Optional[Event] = None
    
    async def serve(self, task_group: TaskGroup, shutdown_event: Event):
        self._task_group = task_group
        self._shutdown_event = shutdown_event

        try:
            await self.connect()

            await self.pub(
                "nats_started", {
                    "timestamp": datetime.now().isoformat()
                }
            )

            await self._shutdown_event.wait()

        finally:
            await self.close()

    async def connect(self):
        if self._connection is None or not self._connection.is_connected:
            try:
                self._connection = await nats.connect(**NATS_CFG)
                logger.info("Connected to NATS server")

                await self._register_pending_handlers()
            except Exception as e:
                logger.error(f"Failed to connect to NATS: {e}")
                raise
    
    async def close(self):
        if self._connection and self._connection.is_connected:
            await self._connection.close()
            self._connection = None
            logger.info("NATS connection closed")
    
    
    async def _register_pending_handlers(self):

        for subject, handler in self.pending_subscribers:
            async def wrapper(msg, h=handler, subj=subject):
                async def handle_safely(msg, h, subj):
                    try:
                        data = json.loads(msg.data.decode()) if msg.data else {}
                        await h(data)
                    except Exception as e:
                        logger.error(f"Error in {subj}: {e}", exc_info=True)
                
                self._task_group.start_soon(handle_safely, msg, h, subj)
            
            await self._connection.subscribe(subject, cb=wrapper)
            logging.info(f"Registered subscription: {subject}")

        for subject, handler in self.pending_responders:
            async def wrapper(msg, h=handler, subj=subject):
                try:
                    data = json.loads(msg.data.decode()) if msg.data else {}
                    result = await h(data)
                    response = json.dumps(result).encode()
                    await msg.respond(response)
                except Exception as e:
                    logger.error(f"Error handling {subj}: {e}")
                    error_response = json.dumps({"error": str(e)}).encode()
                    await msg.respond(error_response)

            await self._connection.subscribe(subject, cb=wrapper)
            logging.info(f"Registered responder: {subject}")

    def sub(self, subject: str):
        def decorator(func: Callable):
            self.pending_subscribers.append((subject, func))
            return func
        return decorator
    
    def reply(self, subject: str):
        def decorator(func: Callable):
            self.pending_responders.append((subject, func))
            return func
        return decorator
    
    async def pub(self, subject: str, data: dict):
        message = json.dumps(data).encode()
        await self._connection.publish(subject, message)

    async def request(self, subject:str, data: dict, timeout: int = 5):
        message = json.dumps(data).encode()
        response = await self._connection.request(subject, message, timeout=timeout)
        return json.loads(response.data.decode()) if response.data else None
    
nc = NATSServer()