import logging

from common.config import FASTAPI_CFG

import uvicorn
from anyio import Event
from anyio.abc import TaskGroup
from uvicorn import Config
from fastapi import FastAPI

import anyio

api = FastAPI(
    title="API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    version=None,
    description=None
)

logger = logging.getLogger("fastapi")

class FastAPIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000):
        self.host = host
        self.port = port
        self.server = None
        
    async def serve(self, task_group: TaskGroup, shutdown_event: Event):
        config = Config(
            app=api,
            host=self.host,
            port=self.port,
            log_level="info",
            loop="none"  # Important: tells uvicorn to use existing loop
        )
        
        self.server = uvicorn.Server(config)
        
        try:
            # Start the server
            task_group.start_soon(self.server.serve)
            logger.info(f"FastAPI server started on {self.host}:{self.port}")
            
            # Wait for shutdown signal
            await shutdown_event.wait()
            
        finally:
            if self.server:
                logger.info("Shutting down FastAPI server...")
                self.server.should_exit = True
                while self.server.started and not self.server.force_exit:
                    await anyio.sleep(0.1)

fastapi_server = FastAPIServer(**FASTAPI_CFG)