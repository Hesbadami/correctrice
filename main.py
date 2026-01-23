import logging
import signal

from common.nats_server import nc
from common.scheduler import sch
from common.fastapi_server import fastapi_server

import handlers
import schedules
import workflows
import endpoints

import anyio
from anyio import run, Event, open_signal_receiver, create_task_group
from anyio.abc import CancelScope

logger = logging.getLogger(__name__)

class Service:
    def __init__(self):
        logger.info("Starting Service")
        self.shutdown_event = Event()
        self._shutdown_initiated = False

    async def start(self):
        try:
            async with create_task_group() as tg:
                # Start NATS server in task group
                tg.start_soon(nc.serve, tg, self.shutdown_event)
                
                # Start FastAPI server
                tg.start_soon(fastapi_server.serve, tg, self.shutdown_event)
            
                # Start scheduler
                if not sch.running:
                    sch.start()
                logger.info("APScheduler Service started successfully")
                
                await self.shutdown_event.wait()
                tg.cancel_scope.cancel()
                
        except Exception as e:
            logger.error(f"Service error: {e}")
            raise
    
    async def stop(self):

        if self._shutdown_initiated:
            return
        
        self._shutdown_initiated = True
        logger.info("Initiating graceful shutdown...")

        # Signal shutdown
        self.shutdown_event.set()

        # Stop scheduler
        logger.info("Stopping APScheduler Service...")
        if sch.running:
            try:
                sch.shutdown(wait=True)
                logger.info("APScheduler Service stopped")
            except Exception as e:
                logger.error(f"Error stopping scheduler: {e}")

    async def signal_handler(self, scope: CancelScope):
        with open_signal_receiver(signal.SIGTERM, signal.SIGINT) as signals:
            async for signum in signals:
                logger.info(f"Received signal {signum}")
                await self.stop()
                scope.cancel()
                return

async def main():
    service = Service()

    try:
        async with create_task_group() as tg:
            tg.start_soon(service.signal_handler, tg.cancel_scope)
            tg.start_soon(service.start)
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except anyio.get_cancelled_exc_class():
        logger.info("Service was cancelled")
    finally:
        await service.stop()
        logger.info("Service shutdown complete")

if __name__ == "__main__":
    run(main)