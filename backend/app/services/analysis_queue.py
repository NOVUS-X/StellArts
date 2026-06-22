import json
import logging

import redis
from redis import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class AnalysisQueueService:
    """
    Service for forwarding validated payloads to the Analysis Node queue.
    Supports Redis and SQS backends.
    """

    def __init__(self):
        self.queue_type = settings.ANALYSIS_QUEUE_TYPE
        self.queue_name = settings.ANALYSIS_QUEUE_NAME
        
        # Initialize Redis client
        if self.queue_type == "redis":
            self.redis_client = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
        
        # Initialize SQS client (if needed in future)
        elif self.queue_type == "sqs":
            import boto3
            self.sqs_client = boto3.client(
                'sqs',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )

    async def enqueue_payload(self, payload: dict) -> bool:
        """
        Enqueue a validated payload for analysis.
        
        Args:
            payload: Dict containing job data and media metadata
            
        Returns:
            True if successfully enqueued
        """
        try:
            if self.queue_type == "redis":
                return await self._enqueue_redis(payload)
            elif self.queue_type == "sqs":
                return await self._enqueue_sqs(payload)
            else:
                raise ValueError(f"Unsupported queue type: {self.queue_type}")
        except Exception as e:
            logger.error(f"Failed to enqueue payload: {e}")
            return False

    async def _enqueue_redis(self, payload: dict) -> bool:
        """Enqueue payload using Redis list."""
        try:
            # Serialize payload to JSON
            payload_json = json.dumps(payload)
            
            # Push to Redis list (left push, right pop for FIFO)
            self.redis_client.lpush(self.queue_name, payload_json)
            
            logger.info(f"Successfully enqueued payload to Redis queue: {self.queue_name}")
            return True
        except Exception as e:
            logger.error(f"Redis enqueue error: {e}")
            raise

    async def _enqueue_sqs(self, payload: dict) -> bool:
        """Enqueue payload using AWS SQS."""
        try:
            # Get queue URL
            response = self.sqs_client.get_queue_url(QueueName=self.queue_name)
            queue_url = response['QueueUrl']
            
            # Send message
            self.sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(payload)
            )
            
            logger.info(f"Successfully enqueued payload to SQS queue: {self.queue_name}")
            return True
        except Exception as e:
            logger.error(f"SQS enqueue error: {e}")
            raise

    async def dequeue_payload(self) -> dict | None:
        """
        Dequeue a payload for processing (used by Analysis Node).
        
        Returns:
            Payload dict or None if queue is empty
        """
        try:
            if self.queue_type == "redis":
                return await self._dequeue_redis()
            elif self.queue_type == "sqs":
                return await self._dequeue_sqs()
            else:
                raise ValueError(f"Unsupported queue type: {self.queue_type}")
        except Exception as e:
            logger.error(f"Failed to dequeue payload: {e}")
            return None

    async def _dequeue_redis(self) -> dict | None:
        """Dequeue payload from Redis list."""
        try:
            # Right pop (FIFO)
            result = self.redis_client.brpop(self.queue_name, timeout=5)
            
            if result:
                _, payload_json = result
                return json.loads(payload_json)
            
            return None
        except Exception as e:
            logger.error(f"Redis dequeue error: {e}")
            return None

    async def _dequeue_sqs(self) -> dict | None:
        """Dequeue payload from SQS."""
        try:
            # Get queue URL
            response = self.sqs_client.get_queue_url(QueueName=self.queue_name)
            queue_url = response['QueueUrl']
            
            # Receive message
            messages = self.sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5
            )
            
            if 'Messages' in messages and messages['Messages']:
                message = messages['Messages'][0]
                payload = json.loads(message['Body'])
                
                # Delete message after receiving
                self.sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                
                return payload
            
            return None
        except Exception as e:
            logger.error(f"SQS dequeue error: {e}")
            return None

    def get_queue_size(self) -> int:
        """Get the current size of the queue."""
        try:
            if self.queue_type == "redis":
                return self.redis_client.llen(self.queue_name)
            elif self.queue_type == "sqs":
                response = self.sqs_client.get_queue_attributes(
                    QueueName=self.queue_name,
                    AttributeNames=['ApproximateNumberOfMessages']
                )
                return int(response['Attributes']['ApproximateNumberOfMessages'])
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
        
        return 0


# Singleton instance
analysis_queue_service = AnalysisQueueService()
