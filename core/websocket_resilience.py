"""
WebSocket Resilience - Mitigación de riesgos de UI/UX

Sistema resiliente de WebSockets con reconexión automática y fallbacks.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import weakref
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Estados de conexión WebSocket."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"

@dataclass
class WSMessage:
    """Mensaje WebSocket con metadata."""
    id: str
    type: str
    data: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1=baja, 2=normal, 3=alta, 4=crítica
    ttl_seconds: int = 300  # Time to live
    retry_count: int = 0
    max_retries: int = 3

    def is_expired(self) -> bool:
        """Verificar si mensaje ha expirado."""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl_seconds)

class WSConnectionManager:
    """Gestor resiliente de conexiones WebSocket."""

    def __init__(self, max_connections: int = 1000):
        self.connections: Dict[str, weakref.ref] = {}
        self.connection_states: Dict[str, ConnectionState] = {}
        self.message_queues: Dict[str, List[WSMessage]] = {}
        self.subscription_topics: Dict[str, Set[str]] = {}  # connection_id -> topics
        self.topic_subscribers: Dict[str, Set[str]] = {}    # topic -> connection_ids
        self.max_connections = max_connections
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "reconnections": 0
        }

    async def add_connection(self, connection_id: str, websocket) -> bool:
        """Agregar conexión con límites."""
        if len(self.connections) >= self.max_connections:
            logger.warning(f"Max connections reached ({self.max_connections})")
            return False

        # Crear weak reference para evitar memory leaks
        self.connections[connection_id] = weakref.ref(websocket)
        self.connection_states[connection_id] = ConnectionState.CONNECTED
        self.message_queues[connection_id] = []
        self.subscription_topics[connection_id] = set()

        self.stats["total_connections"] += 1
        self.stats["active_connections"] += 1

        logger.info(f"WebSocket connection added: {connection_id}")
        return True

    async def remove_connection(self, connection_id: str):
        """Remover conexión y limpiar recursos."""
        if connection_id in self.connections:
            # Limpiar suscripciones
            topics = self.subscription_topics.get(connection_id, set())
            for topic in topics:
                if topic in self.topic_subscribers:
                    self.topic_subscribers[topic].discard(connection_id)
                    if not self.topic_subscribers[topic]:
                        del self.topic_subscribers[topic]

            # Limpiar conexión
            del self.connections[connection_id]
            del self.connection_states[connection_id]
            del self.message_queues[connection_id]
            del self.subscription_topics[connection_id]

            self.stats["active_connections"] -= 1

            logger.info(f"WebSocket connection removed: {connection_id}")

    async def subscribe_to_topic(self, connection_id: str, topic: str):
        """Suscribir conexión a tópico."""
        if connection_id not in self.connections:
            return False

        self.subscription_topics[connection_id].add(topic)

        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = set()
        self.topic_subscribers[topic].add(connection_id)

        logger.debug(f"Connection {connection_id} subscribed to {topic}")
        return True

    async def send_to_connection(
        self,
        connection_id: str,
        message: WSMessage,
        fallback_to_queue: bool = True
    ) -> bool:
        """Enviar mensaje a conexión específica."""
        if connection_id not in self.connections:
            return False

        websocket_ref = self.connections[connection_id]
        websocket = websocket_ref()

        if websocket is None:
            # Conexión garbage collected, limpiar
            await self.remove_connection(connection_id)
            return False

        try:
            # Verificar estado de conexión
            if self.connection_states[connection_id] != ConnectionState.CONNECTED:
                if fallback_to_queue:
                    await self._queue_message(connection_id, message)
                return False

            # Enviar mensaje
            message_data = {
                "id": message.id,
                "type": message.type,
                "data": message.data,
                "timestamp": message.timestamp.isoformat()
            }

            await websocket.send_text(json.dumps(message_data))
            self.stats["messages_sent"] += 1

            logger.debug(f"Message sent to {connection_id}: {message.type}")
            return True

        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            self.stats["messages_failed"] += 1

            # Marcar conexión como desconectada
            self.connection_states[connection_id] = ConnectionState.DISCONNECTED

            if fallback_to_queue:
                await self._queue_message(connection_id, message)

            return False

    async def broadcast_to_topic(self, topic: str, message: WSMessage) -> int:
        """Broadcast mensaje a todos los suscriptores de un tópico."""
        if topic not in self.topic_subscribers:
            logger.debug(f"No subscribers for topic: {topic}")
            return 0

        subscribers = self.topic_subscribers[topic].copy()
        successful_sends = 0

        # Enviar a todos los suscriptores
        for connection_id in subscribers:
            if await self.send_to_connection(connection_id, message):
                successful_sends += 1

        logger.info(f"Broadcast to {topic}: {successful_sends}/{len(subscribers)} successful")
        return successful_sends

    async def _queue_message(self, connection_id: str, message: WSMessage):
        """Encolar mensaje para envío posterior."""
        if connection_id not in self.message_queues:
            return

        queue = self.message_queues[connection_id]

        # Limpiar mensajes expirados
        queue[:] = [msg for msg in queue if not msg.is_expired()]

        # Agregar nuevo mensaje
        queue.append(message)

        # Mantener solo los últimos 100 mensajes por conexión
        if len(queue) > 100:
            # Ordenar por prioridad y timestamp, mantener los más importantes
            queue.sort(key=lambda x: (x.priority, x.timestamp), reverse=True)
            queue[:] = queue[:100]

        logger.debug(f"Message queued for {connection_id}: {message.type}")

    async def process_queued_messages(self, connection_id: str) -> int:
        """Procesar mensajes encolados para una conexión."""
        if connection_id not in self.message_queues:
            return 0

        if self.connection_states.get(connection_id) != ConnectionState.CONNECTED:
            return 0

        queue = self.message_queues[connection_id]
        processed = 0
        failed_messages = []

        for message in queue[:]:
            if message.is_expired():
                queue.remove(message)
                continue

            if await self.send_to_connection(connection_id, message, fallback_to_queue=False):
                queue.remove(message)
                processed += 1
            else:
                message.retry_count += 1
                if message.retry_count >= message.max_retries:
                    queue.remove(message)
                    failed_messages.append(message)
                else:
                    failed_messages.append(message)
                break  # Stop processing if one fails

        # Log failed messages
        for msg in failed_messages:
            if msg.retry_count >= msg.max_retries:
                logger.warning(f"Message {msg.id} dropped after {msg.retry_count} retries")

        logger.info(f"Processed {processed} queued messages for {connection_id}")
        return processed

    async def cleanup_stale_connections(self):
        """Limpiar conexiones obsoletas."""
        stale_connections = []

        for connection_id, websocket_ref in self.connections.items():
            websocket = websocket_ref()
            if websocket is None:
                stale_connections.append(connection_id)

        for connection_id in stale_connections:
            await self.remove_connection(connection_id)

        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale connections")

    def get_connection_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de conexiones."""
        return {
            **self.stats,
            "queued_messages": sum(len(queue) for queue in self.message_queues.values()),
            "active_topics": len(self.topic_subscribers),
            "total_subscriptions": sum(len(subs) for subs in self.topic_subscribers.values())
        }

class ResilientWebSocketHandler:
    """Handler resiliente para WebSockets con reconexión automática."""

    def __init__(self, connection_manager: WSConnectionManager):
        self.connection_manager = connection_manager
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}

    @asynccontextmanager
    async def handle_connection(self, websocket, connection_id: str):
        """Context manager para manejar conexión WebSocket."""
        try:
            # Agregar conexión
            if not await self.connection_manager.add_connection(connection_id, websocket):
                raise Exception("Cannot accept connection: limit reached")

            # Iniciar heartbeat
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(connection_id, websocket)
            )
            self.heartbeat_tasks[connection_id] = heartbeat_task

            # Procesar mensajes encolados
            await self.connection_manager.process_queued_messages(connection_id)

            yield connection_id

        except Exception as e:
            logger.error(f"WebSocket connection error for {connection_id}: {e}")
            raise
        finally:
            # Limpiar recursos
            if connection_id in self.heartbeat_tasks:
                self.heartbeat_tasks[connection_id].cancel()
                del self.heartbeat_tasks[connection_id]

            await self.connection_manager.remove_connection(connection_id)

    async def _heartbeat_loop(self, connection_id: str, websocket):
        """Loop de heartbeat para detectar conexiones muertas."""
        try:
            while True:
                await asyncio.sleep(30)  # Ping cada 30 segundos

                try:
                    await websocket.ping()
                    logger.debug(f"Heartbeat sent to {connection_id}")
                except Exception:
                    logger.warning(f"Heartbeat failed for {connection_id}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat error for {connection_id}: {e}")

class AutomationWebSocketService:
    """Servicio WebSocket específico para automatización."""

    def __init__(self):
        self.connection_manager = WSConnectionManager()
        self.handler = ResilientWebSocketHandler(self.connection_manager)

    async def send_automation_update(
        self,
        job_id: int,
        update_type: str,
        data: Dict[str, Any],
        priority: int = 2
    ):
        """Enviar actualización de automatización."""
        message = WSMessage(
            id=f"automation_{job_id}_{int(time.time())}",
            type="automation_update",
            data={
                "job_id": job_id,
                "update_type": update_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            },
            timestamp=datetime.now(),
            priority=priority
        )

        topic = f"automation_job_{job_id}"
        return await self.connection_manager.broadcast_to_topic(topic, message)

    async def send_progress_update(self, job_id: int, progress: float, message: str):
        """Enviar actualización de progreso."""
        await self.send_automation_update(
            job_id, "progress",
            {"progress": progress, "message": message},
            priority=3
        )

    async def send_error_notification(self, job_id: int, error: str, screenshot_path: Optional[str] = None):
        """Enviar notificación de error."""
        await self.send_automation_update(
            job_id, "error",
            {"error": error, "screenshot_path": screenshot_path},
            priority=4
        )

    async def send_completion_notification(self, job_id: int, result: Dict[str, Any]):
        """Enviar notificación de completado."""
        await self.send_automation_update(
            job_id, "completed",
            {"result": result},
            priority=3
        )

    async def subscribe_to_job(self, connection_id: str, job_id: int):
        """Suscribir conexión a actualizaciones de job."""
        topic = f"automation_job_{job_id}"
        return await self.connection_manager.subscribe_to_topic(connection_id, topic)

    async def handle_websocket(self, websocket, connection_id: str):
        """Manejar conexión WebSocket."""
        async with self.handler.handle_connection(websocket, connection_id):
            try:
                async for message in websocket.iter_text():
                    await self._handle_message(connection_id, message)
            except Exception as e:
                logger.error(f"WebSocket message handling error: {e}")

    async def _handle_message(self, connection_id: str, message: str):
        """Procesar mensaje recibido."""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type == "subscribe_job":
                job_id = data.get("job_id")
                if job_id:
                    await self.subscribe_to_job(connection_id, job_id)

            elif message_type == "ping":
                # Respond to ping
                pong_message = WSMessage(
                    id=f"pong_{int(time.time())}",
                    type="pong",
                    data={"timestamp": datetime.now().isoformat()},
                    timestamp=datetime.now()
                )
                await self.connection_manager.send_to_connection(connection_id, pong_message)

        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del servicio."""
        return self.connection_manager.get_connection_stats()

# Global instance
automation_ws_service = AutomationWebSocketService()

# Background task para cleanup
async def websocket_cleanup_task():
    """Tarea de background para limpiar conexiones."""
    while True:
        try:
            await automation_ws_service.connection_manager.cleanup_stale_connections()
            await asyncio.sleep(60)  # Cada minuto
        except Exception as e:
            logger.error(f"WebSocket cleanup error: {e}")
            await asyncio.sleep(10)