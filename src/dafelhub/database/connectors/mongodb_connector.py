"""
MongoDB Connector
Enterprise-grade MongoDB database connector with advanced capabilities
"""

import asyncio
import time
import uuid
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Union, AsyncGenerator, 
    Callable, Tuple, AsyncIterator
)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import (
    PyMongoError, ConnectionFailure, AuthenticationFailed, 
    ConfigurationError, OperationFailure, NetworkTimeout
)
from bson import ObjectId
import re
import sys

from dafelhub.core.connections import (
    IDataSourceConnector, ConnectionConfig, ConnectionMetadata, 
    QueryResult, ConnectionError, ConnectionErrorType, ConnectionStatus
)
from dafelhub.core.logging import get_logger, LoggerMixin


logger = get_logger(__name__)


class MongoOperationType(Enum):
    """MongoDB Operation types for optimization"""
    FIND = "FIND"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    AGGREGATE = "AGGREGATE"
    INDEX = "INDEX"
    COMMAND = "COMMAND"


@dataclass
class MongoQueryMetrics:
    """MongoDB query execution metrics"""
    query_id: str
    operation_type: MongoOperationType
    collection: str
    query: Dict[str, Any]
    parameters: Optional[Dict[str, Any]]
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_time: Optional[float] = None
    documents_examined: int = 0
    documents_returned: int = 0
    documents_modified: int = 0
    index_used: bool = False
    connection_id: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds"""
        if self.execution_time is not None:
            return self.execution_time * 1000
        return 0.0


@dataclass
class MongoConnectionPoolMetrics:
    """MongoDB connection pool metrics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    max_connections: int = 0
    min_connections: int = 0
    total_operations: int = 0
    failed_operations: int = 0
    avg_operation_time: float = 0.0
    pool_created_at: datetime = field(default_factory=datetime.now)
    last_activity: Optional[datetime] = None


class MongoQueryBuilder:
    """MongoDB query builder for complex queries"""
    
    def __init__(self):
        self.pipeline = []
        self.query_filter = {}
        self.projection = None
        self.sort_spec = None
        self.limit_count = None
        self.skip_count = None
    
    def match(self, conditions: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add match stage to aggregation pipeline"""
        self.pipeline.append({"$match": conditions})
        return self
    
    def project(self, projection: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add projection stage"""
        self.pipeline.append({"$project": projection})
        self.projection = projection
        return self
    
    def sort(self, sort_spec: Dict[str, int]) -> 'MongoQueryBuilder':
        """Add sort stage"""
        self.pipeline.append({"$sort": sort_spec})
        self.sort_spec = sort_spec
        return self
    
    def limit(self, count: int) -> 'MongoQueryBuilder':
        """Add limit stage"""
        self.pipeline.append({"$limit": count})
        self.limit_count = count
        return self
    
    def skip(self, count: int) -> 'MongoQueryBuilder':
        """Add skip stage"""
        self.pipeline.append({"$skip": count})
        self.skip_count = count
        return self
    
    def group(self, group_spec: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add group stage"""
        self.pipeline.append({"$group": group_spec})
        return self
    
    def lookup(self, from_collection: str, local_field: str, 
               foreign_field: str, as_field: str) -> 'MongoQueryBuilder':
        """Add lookup (join) stage"""
        self.pipeline.append({
            "$lookup": {
                "from": from_collection,
                "localField": local_field,
                "foreignField": foreign_field,
                "as": as_field
            }
        })
        return self
    
    def unwind(self, field: str, preserve_null: bool = False) -> 'MongoQueryBuilder':
        """Add unwind stage"""
        unwind_spec = {"path": f"${field}"}
        if preserve_null:
            unwind_spec["preserveNullAndEmptyArrays"] = True
        self.pipeline.append({"$unwind": unwind_spec})
        return self
    
    def where(self, conditions: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Set filter conditions for find operations"""
        self.query_filter = conditions
        return self
    
    def build_find_query(self) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Build find query and projection"""
        return self.query_filter, self.projection
    
    def build_aggregation(self) -> List[Dict[str, Any]]:
        """Build aggregation pipeline"""
        return self.pipeline
    
    def clear(self) -> 'MongoQueryBuilder':
        """Clear all query components"""
        self.pipeline = []
        self.query_filter = {}
        self.projection = None
        self.sort_spec = None
        self.limit_count = None
        self.skip_count = None
        return self


class MongoQueryStream:
    """Async MongoDB query streaming implementation"""
    
    def __init__(self, collection: AsyncIOMotorCollection, query: Dict[str, Any], 
                 projection: Optional[Dict[str, Any]] = None, 
                 batch_size: int = 1000):
        self.collection = collection
        self.query = query
        self.projection = projection
        self.batch_size = batch_size
        self._cursor = None
        self._exhausted = False
    
    async def __aenter__(self):
        """Enter async context"""
        self._cursor = self.collection.find(
            self.query, 
            self.projection,
            batch_size=self.batch_size
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context"""
        if self._cursor:
            self._cursor.close()
    
    async def __aiter__(self):
        """Async iterator"""
        if not self._cursor:
            raise RuntimeError("Stream must be used within async context manager")
        
        batch = []
        async for document in self._cursor:
            batch.append(document)
            if len(batch) >= self.batch_size:
                yield batch
                batch = []
        
        if batch:  # Yield remaining documents
            yield batch


class MongoDBConnector(IDataSourceConnector, LoggerMixin):
    """
    Enterprise MongoDB Connector with advanced features:
    - Connection pooling with Motor (async)
    - Document streaming for large collections
    - Schema discovery with collection analysis
    - Query builder for complex operations
    - Aggregation pipeline support
    - Comprehensive error handling
    - Performance monitoring
    - Health checks and server version detection
    - Index analysis and optimization suggestions
    """
    
    def __init__(self, config: ConnectionConfig):
        self.id = config.id
        self.config = config
        self._client: Optional[AsyncIOMotorClient] = None
        self._database: Optional[AsyncIOMotorDatabase] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._metadata = ConnectionMetadata()
        self._pool_metrics = MongoConnectionPoolMetrics()
        self._query_history: List[MongoQueryMetrics] = []
        self._active_operations: Dict[str, MongoQueryMetrics] = {}
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._server_info: Dict[str, Any] = {}
        self._connection_semaphore: Optional[asyncio.Semaphore] = None
        self._query_builder = MongoQueryBuilder()
        
        # Configuration
        self.query_history_size = config.configuration.get('query_history_size', 10000)
        self.streaming_batch_size = config.configuration.get('streaming_batch_size', 1000)
        self.health_check_interval = config.configuration.get('health_check_interval', 30)
        self.cleanup_interval = config.configuration.get('cleanup_interval', 300)
        
        self.logger.info(f"MongoDB connector initialized: {self.id}")
    
    @property
    def status(self) -> ConnectionStatus:
        """Current connection status"""
        return self._status
    
    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return self._metadata.is_healthy and self._client is not None
    
    @property
    def query_builder(self) -> MongoQueryBuilder:
        """Get query builder instance"""
        return self._query_builder.clear()
    
    async def connect(self) -> None:
        """Establish MongoDB connection with enterprise features"""
        if self._client is not None:
            self.logger.warning(f"MongoDB connection already exists: {self.id}")
            return
        
        self._status = ConnectionStatus.CONNECTING
        start_time = time.time()
        
        try:
            # Build connection URI
            uri = self._build_connection_uri()
            
            # Create MongoDB client
            self._client = AsyncIOMotorClient(
                uri,
                maxPoolSize=self.config.configuration.get('max_pool_size', self.config.pool_size),
                minPoolSize=self.config.configuration.get('min_pool_size', 2),
                maxIdleTimeMS=self.config.configuration.get('max_idle_time_ms', 300000),
                waitQueueTimeoutMS=self.config.configuration.get('wait_queue_timeout_ms', 10000),
                connectTimeoutMS=self.config.connection_timeout or 10000,
                socketTimeoutMS=self.config.query_timeout or 20000,
                serverSelectionTimeoutMS=self.config.configuration.get('server_selection_timeout_ms', 30000),
                heartbeatFrequencyMS=self.config.configuration.get('heartbeat_frequency_ms', 10000),
                retryWrites=self.config.configuration.get('retry_writes', True),
                retryReads=self.config.configuration.get('retry_reads', True),
                compressors=self.config.configuration.get('compressors', ['zstd', 'zlib']),
                zlibCompressionLevel=self.config.configuration.get('zlib_compression_level', 6)
            )
            
            # Get database
            self._database = self._client[self.config.database]
            
            # Test connection
            await self._test_connection()
            
            # Initialize pool metrics
            self._pool_metrics = MongoConnectionPoolMetrics(
                max_connections=self.config.pool_size,
                min_connections=self.config.configuration.get('min_pool_size', 2),
                pool_created_at=datetime.now()
            )
            
            # Update metadata
            self._metadata.connected_at = datetime.now()
            self._metadata.is_healthy = True
            self._metadata.server_info = self._server_info
            self._status = ConnectionStatus.CONNECTED
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Initialize semaphore for operation limiting
            self._connection_semaphore = asyncio.Semaphore(self.config.pool_size)
            
            duration = time.time() - start_time
            self.logger.info(f"MongoDB connected successfully: {self.id} ({duration:.2f}s)", 
                           extra_data={
                               "pool_size": f"{self._pool_metrics.min_connections}-{self._pool_metrics.max_connections}",
                               "server_version": self._server_info.get('version', 'unknown'),
                               "database": self.config.database
                           })
            
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            duration = time.time() - start_time
            error = self._handle_error(e)
            self.logger.error(f"Failed to connect MongoDB: {self.id} ({duration:.2f}s)", 
                            extra_data={"error": str(error)})
            raise error
    
    async def disconnect(self) -> None:
        """Close MongoDB connection gracefully"""
        if self._client is None:
            return
        
        self.logger.info(f"Disconnecting MongoDB: {self.id}")
        self._status = ConnectionStatus.DISCONNECTED
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Wait for active operations to complete (with timeout)
            await self._wait_for_active_operations(timeout=30.0)
            
            # Cancel background tasks
            if self._health_task and not self._health_task.done():
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            if self._cleanup_task and not self._cleanup_task.done():
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Close client
            self._client.close()
            self._client = None
            self._database = None
            
            # Update metadata
            self._metadata.is_healthy = False
            self._metadata.last_activity = datetime.now()
            
            self.logger.info(f"MongoDB disconnected: {self.id}")
            
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Error disconnecting MongoDB: {self.id}", 
                            extra_data={"error": str(error)})
            raise error
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test MongoDB connection and gather server information"""
        if not self._client:
            return {
                "success": False,
                "message": "No MongoDB client available",
                "response_time": 0
            }
        
        start_time = time.time()
        
        try:
            # Get server information
            server_info = await self._client.server_info()
            
            # Get database stats
            db_stats = await self._database.command("dbStats")
            
            # Get connection info
            is_master = await self._database.command("ismaster")
            
            response_time = time.time() - start_time
            
            server_data = {
                'version': server_info.get('version', 'unknown'),
                'git_version': server_info.get('gitVersion', 'unknown'),
                'platform': server_info.get('targetMinOS', 'unknown'),
                'database': self.config.database,
                'collections': db_stats.get('collections', 0),
                'data_size': db_stats.get('dataSize', 0),
                'storage_size': db_stats.get('storageSize', 0),
                'index_size': db_stats.get('indexSize', 0),
                'is_master': is_master.get('ismaster', False),
                'max_bson_object_size': is_master.get('maxBsonObjectSize', 0),
                'max_message_size_bytes': is_master.get('maxMessageSizeBytes', 0)
            }
            
            self._server_info = server_data
            
            return {
                "success": True,
                "message": "Connection successful",
                "response_time": response_time,
                "server_info": server_data
            }
        
        except Exception as e:
            response_time = time.time() - start_time
            error = self._handle_error(e)
            
            return {
                "success": False,
                "message": str(error),
                "response_time": response_time
            }
    
    async def health_check(self) -> bool:
        """Quick MongoDB health check"""
        if not self._client:
            return False
        
        try:
            async with asyncio.timeout(5.0):  # 5 second timeout
                await self._client.admin.command('ping')
                self._metadata.is_healthy = True
                self._metadata.last_activity = datetime.now()
                return True
        
        except Exception as e:
            self._metadata.is_healthy = False
            self._metadata.last_error = str(e)
            self.logger.warning(f"Health check failed: {self.id}", extra_data={"error": str(e)})
            return False
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """Execute a MongoDB operation with comprehensive monitoring"""
        if not self._database:
            raise ConnectionError(
                "No MongoDB database available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        # Parse MongoDB-style query
        try:
            operation_data = json.loads(query) if isinstance(query, str) else query
        except json.JSONDecodeError:
            return QueryResult(
                success=False,
                error="Invalid JSON query format",
                execution_time=0
            )
        
        operation_id = str(uuid.uuid4())
        operation_type = self._detect_operation_type(operation_data)
        collection_name = operation_data.get('collection', 'unknown')
        parameters = params or {}
        
        # Create operation metrics
        metrics = MongoQueryMetrics(
            query_id=operation_id,
            operation_type=operation_type,
            collection=collection_name,
            query=operation_data,
            parameters=parameters,
            start_time=datetime.now()
        )
        
        self._active_operations[operation_id] = metrics
        
        try:
            async with self._connection_semaphore:
                collection = self._database[collection_name]
                
                start_execution = time.time()
                
                # Execute operation based on type
                if operation_type == MongoOperationType.FIND:
                    filter_query = operation_data.get('filter', {})
                    projection = operation_data.get('projection')
                    limit = operation_data.get('limit')
                    skip = operation_data.get('skip')
                    sort = operation_data.get('sort')
                    
                    cursor = collection.find(filter_query, projection)
                    if sort:
                        cursor = cursor.sort(list(sort.items()))
                    if skip:
                        cursor = cursor.skip(skip)
                    if limit:
                        cursor = cursor.limit(limit)
                    
                    result = await cursor.to_list(length=None)
                    data = [self._convert_objectid(doc) for doc in result]
                    documents_returned = len(data)
                    documents_modified = 0
                
                elif operation_type == MongoOperationType.INSERT:
                    documents = operation_data.get('documents', [])
                    if len(documents) == 1:
                        result = await collection.insert_one(documents[0])
                        data = {'inserted_id': str(result.inserted_id)}
                        documents_modified = 1
                    else:
                        result = await collection.insert_many(documents)
                        data = {'inserted_ids': [str(id) for id in result.inserted_ids]}
                        documents_modified = len(result.inserted_ids)
                    documents_returned = 0
                
                elif operation_type == MongoOperationType.UPDATE:
                    filter_query = operation_data.get('filter', {})
                    update_doc = operation_data.get('update', {})
                    upsert = operation_data.get('upsert', False)
                    multi = operation_data.get('multi', False)
                    
                    if multi:
                        result = await collection.update_many(filter_query, update_doc, upsert=upsert)
                    else:
                        result = await collection.update_one(filter_query, update_doc, upsert=upsert)
                    
                    data = {
                        'matched_count': result.matched_count,
                        'modified_count': result.modified_count,
                        'upserted_id': str(result.upserted_id) if result.upserted_id else None
                    }
                    documents_returned = 0
                    documents_modified = result.modified_count
                
                elif operation_type == MongoOperationType.DELETE:
                    filter_query = operation_data.get('filter', {})
                    multi = operation_data.get('multi', False)
                    
                    if multi:
                        result = await collection.delete_many(filter_query)
                    else:
                        result = await collection.delete_one(filter_query)
                    
                    data = {'deleted_count': result.deleted_count}
                    documents_returned = 0
                    documents_modified = result.deleted_count
                
                elif operation_type == MongoOperationType.AGGREGATE:
                    pipeline = operation_data.get('pipeline', [])
                    cursor = collection.aggregate(pipeline)
                    result = await cursor.to_list(length=None)
                    data = [self._convert_objectid(doc) for doc in result]
                    documents_returned = len(data)
                    documents_modified = 0
                
                else:
                    raise ConnectionError(
                        f"Unsupported operation type: {operation_type}",
                        ConnectionErrorType.INVALID_CONFIGURATION
                    )
                
                execution_time = time.time() - start_execution
                
                # Update metrics
                metrics.end_time = datetime.now()
                metrics.execution_time = execution_time
                metrics.documents_returned = documents_returned
                metrics.documents_modified = documents_modified
                
                # Update pool metrics
                self._update_pool_metrics(True, execution_time)
                
                # Store in history
                self._store_operation_metrics(metrics)
                
                return QueryResult(
                    success=True,
                    data=data,
                    metadata={
                        'operation_id': operation_id,
                        'execution_time': execution_time,
                        'documents_returned': documents_returned,
                        'documents_modified': documents_modified,
                        'operation_type': operation_type.value,
                        'collection': collection_name
                    },
                    execution_time=execution_time
                )
        
        except Exception as e:
            execution_time = time.time() - metrics.start_time.timestamp()
            metrics.end_time = datetime.now()
            metrics.execution_time = execution_time
            metrics.error = str(e)
            
            # Update pool metrics
            self._update_pool_metrics(False, execution_time)
            
            # Store failed operation in history
            self._store_operation_metrics(metrics)
            
            error = self._handle_error(e)
            self.logger.error(f"Operation execution failed: {operation_id}", 
                            extra_data={
                                "error": str(error),
                                "operation_type": operation_type.value,
                                "execution_time": execution_time
                            })
            
            return QueryResult(
                success=False,
                error=str(error),
                execution_time=execution_time
            )
        
        finally:
            # Remove from active operations
            self._active_operations.pop(operation_id, None)
    
    async def stream_query(self, query: str, params: Optional[Dict[str, Any]] = None, 
                          batch_size: int = None) -> AsyncIterator[List[Dict[str, Any]]]:
        """Stream large MongoDB collection results"""
        if not self._database:
            raise ConnectionError(
                "No MongoDB database available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        batch_size = batch_size or self.streaming_batch_size
        
        try:
            operation_data = json.loads(query) if isinstance(query, str) else query
        except json.JSONDecodeError:
            raise ConnectionError(
                "Invalid JSON query format",
                ConnectionErrorType.INVALID_CONFIGURATION
            )
        
        collection_name = operation_data.get('collection', 'unknown')
        filter_query = operation_data.get('filter', {})
        projection = operation_data.get('projection')
        
        self.logger.info(f"Starting MongoDB query stream: {self.id}", 
                        extra_data={
                            "collection": collection_name,
                            "batch_size": batch_size,
                            "filter_preview": str(filter_query)[:100]
                        })
        
        collection = self._database[collection_name]
        stream = MongoQueryStream(collection, filter_query, projection, batch_size)
        
        async with stream:
            async for batch in stream:
                yield [self._convert_objectid(doc) for doc in batch]
    
    async def get_schema_info(self, collection_name: str = None) -> Dict[str, Any]:
        """Get comprehensive MongoDB schema information with metadata"""
        if not self._database:
            raise ConnectionError(
                "No MongoDB database available",
                ConnectionErrorType.CONNECTION_REFUSED
            )
        
        schema_info = {
            'database_name': self.config.database,
            'collections': [],
            'indexes': [],
            'database_stats': {}
        }
        
        try:
            # Get database stats
            db_stats = await self._database.command("dbStats")
            schema_info['database_stats'] = {
                'collections': db_stats.get('collections', 0),
                'data_size': db_stats.get('dataSize', 0),
                'storage_size': db_stats.get('storageSize', 0),
                'index_size': db_stats.get('indexSize', 0),
                'file_size': db_stats.get('fileSize', 0),
                'avg_obj_size': db_stats.get('avgObjSize', 0)
            }
            
            # Get collection list
            collection_names = await self._database.list_collection_names()
            
            # Filter to specific collection if requested
            if collection_name:
                collection_names = [collection_name] if collection_name in collection_names else []
            
            for coll_name in collection_names:
                collection = self._database[coll_name]
                
                # Get collection stats
                try:
                    coll_stats = await self._database.command("collStats", coll_name)
                except:
                    coll_stats = {}
                
                # Get indexes
                indexes = []
                async for index in collection.list_indexes():
                    indexes.append({
                        'name': index.get('name'),
                        'key': index.get('key'),
                        'unique': index.get('unique', False),
                        'sparse': index.get('sparse', False),
                        'background': index.get('background', False)
                    })
                
                # Sample documents to infer schema
                sample_docs = await collection.find().limit(100).to_list(length=100)
                inferred_schema = self._infer_schema(sample_docs)
                
                collection_info = {
                    'name': coll_name,
                    'count': coll_stats.get('count', 0),
                    'size': coll_stats.get('size', 0),
                    'storage_size': coll_stats.get('storageSize', 0),
                    'avg_obj_size': coll_stats.get('avgObjSize', 0),
                    'indexes': indexes,
                    'inferred_schema': inferred_schema,
                    'capped': coll_stats.get('capped', False),
                    'max': coll_stats.get('max', None)
                }
                
                schema_info['collections'].append(collection_info)
                schema_info['indexes'].extend(indexes)
        
        except Exception as e:
            error = self._handle_error(e)
            self.logger.error(f"Failed to get schema info", extra_data={"error": str(error)})
            raise error
        
        return schema_info
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive MongoDB performance metrics"""
        current_time = datetime.now()
        
        # Calculate operation statistics
        total_operations = len(self._query_history)
        failed_operations = sum(1 for q in self._query_history if q.error)
        
        if total_operations > 0:
            avg_execution_time = sum(q.execution_time or 0 for q in self._query_history) / total_operations
            success_rate = (total_operations - failed_operations) / total_operations * 100
        else:
            avg_execution_time = 0
            success_rate = 100
        
        # Operation type distribution
        operation_type_stats = {}
        for operation in self._query_history:
            ot = operation.operation_type.value
            if ot not in operation_type_stats:
                operation_type_stats[ot] = {'count': 0, 'avg_time': 0, 'total_time': 0}
            operation_type_stats[ot]['count'] += 1
            operation_type_stats[ot]['total_time'] += operation.execution_time or 0
        
        for ot_stats in operation_type_stats.values():
            if ot_stats['count'] > 0:
                ot_stats['avg_time'] = ot_stats['total_time'] / ot_stats['count']
        
        return {
            'connection_id': self.id,
            'status': self._status.value,
            'uptime_seconds': (current_time - self._metadata.connected_at).total_seconds() 
                            if self._metadata.connected_at else 0,
            'pool_metrics': {
                'max_size': self._pool_metrics.max_connections,
                'min_size': self._pool_metrics.min_connections,
            },
            'operation_metrics': {
                'total_operations': total_operations,
                'failed_operations': failed_operations,
                'success_rate': success_rate,
                'avg_execution_time': avg_execution_time,
                'active_operations': len(self._active_operations),
                'operation_type_distribution': operation_type_stats
            },
            'server_info': self._server_info,
            'last_activity': self._metadata.last_activity.isoformat() 
                           if self._metadata.last_activity else None
        }
    
    # Private methods
    
    def _build_connection_uri(self) -> str:
        """Build MongoDB connection URI from configuration"""
        if 'connection_string' in self.config.configuration:
            return self.config.configuration['connection_string']
        
        # Build URI components
        auth_part = f"{self.config.username}:{self.config.password}@" if self.config.username else ""
        host_part = f"{self.config.host}:{self.config.port}"
        
        uri_parts = [f"mongodb://{auth_part}{host_part}/{self.config.database}"]
        
        # Add connection parameters
        params = []
        if self.config.ssl:
            params.append("ssl=true")
        
        # Add custom parameters
        for key, value in self.config.configuration.get('connection_params', {}).items():
            params.append(f"{key}={value}")
        
        if params:
            uri_parts.append("?" + "&".join(params))
        
        return "".join(uri_parts)
    
    async def _test_connection(self) -> None:
        """Test MongoDB connection during startup"""
        await self._client.admin.command('ping')
    
    async def _start_background_tasks(self) -> None:
        """Start background monitoring tasks"""
        # Health check task
        self._health_task = asyncio.create_task(self._health_check_loop())
        
        # Cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _health_check_loop(self) -> None:
        """Background health check loop"""
        while not self._shutdown_event.is_set():
            try:
                await self.health_check()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check loop error: {self.id}", extra_data={"error": str(e)})
                await asyncio.sleep(5)  # Short sleep on error
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while not self._shutdown_event.is_set():
            try:
                await self._cleanup_query_history()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {self.id}", extra_data={"error": str(e)})
                await asyncio.sleep(30)  # Longer sleep on error
    
    async def _cleanup_query_history(self) -> None:
        """Clean up old operation history"""
        if len(self._query_history) > self.query_history_size:
            # Keep only the most recent operations
            self._query_history = self._query_history[-self.query_history_size:]
    
    async def _wait_for_active_operations(self, timeout: float = 30.0) -> None:
        """Wait for active operations to complete"""
        start_time = time.time()
        
        while self._active_operations and (time.time() - start_time) < timeout:
            await asyncio.sleep(0.1)
        
        if self._active_operations:
            self.logger.warning(f"Timeout waiting for {len(self._active_operations)} active operations")
    
    def _detect_operation_type(self, operation_data: Dict[str, Any]) -> MongoOperationType:
        """Detect operation type from MongoDB operation data"""
        if 'filter' in operation_data and 'update' not in operation_data and 'documents' not in operation_data:
            return MongoOperationType.FIND
        elif 'documents' in operation_data:
            return MongoOperationType.INSERT
        elif 'update' in operation_data:
            return MongoOperationType.UPDATE
        elif 'filter' in operation_data and any(key in operation_data for key in ['delete', 'remove']):
            return MongoOperationType.DELETE
        elif 'pipeline' in operation_data:
            return MongoOperationType.AGGREGATE
        elif any(key in operation_data for key in ['createIndex', 'dropIndex']):
            return MongoOperationType.INDEX
        else:
            return MongoOperationType.COMMAND
    
    def _update_pool_metrics(self, success: bool, execution_time: float) -> None:
        """Update pool metrics"""
        self._pool_metrics.total_operations += 1
        self._pool_metrics.last_activity = datetime.now()
        
        if not success:
            self._pool_metrics.failed_operations += 1
        
        # Update average operation time
        if self._pool_metrics.total_operations == 1:
            self._pool_metrics.avg_operation_time = execution_time
        else:
            # Exponential moving average
            alpha = 0.1
            self._pool_metrics.avg_operation_time = (
                alpha * execution_time + 
                (1 - alpha) * self._pool_metrics.avg_operation_time
            )
    
    def _store_operation_metrics(self, metrics: MongoQueryMetrics) -> None:
        """Store operation metrics in history"""
        self._query_history.append(metrics)
        
        # Limit history size
        if len(self._query_history) > self.query_history_size:
            self._query_history.pop(0)
    
    def _convert_objectid(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ObjectId instances to strings for JSON serialization"""
        if isinstance(document, dict):
            return {
                key: str(value) if isinstance(value, ObjectId) else 
                     self._convert_objectid(value) if isinstance(value, dict) else
                     [self._convert_objectid(item) for item in value] if isinstance(value, list) else
                     value
                for key, value in document.items()
            }
        return document
    
    def _infer_schema(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Infer schema from sample documents"""
        if not documents:
            return {}
        
        schema = {}
        
        for doc in documents:
            for key, value in doc.items():
                if key not in schema:
                    schema[key] = {
                        'types': set(),
                        'nullable': False,
                        'example': value
                    }
                
                if value is None:
                    schema[key]['nullable'] = True
                else:
                    schema[key]['types'].add(type(value).__name__)
        
        # Convert sets to lists for JSON serialization
        for key, info in schema.items():
            info['types'] = list(info['types'])
        
        return schema
    
    def _handle_error(self, error: Exception) -> ConnectionError:
        """Handle and classify MongoDB errors"""
        error_type = ConnectionErrorType.UNKNOWN
        error_code = "UNKNOWN"
        
        if isinstance(error, AuthenticationFailed):
            error_type = ConnectionErrorType.AUTHENTICATION_FAILED
            error_code = 'AUTH_FAILED'
        
        elif isinstance(error, ConnectionFailure):
            error_type = ConnectionErrorType.CONNECTION_REFUSED
            error_code = 'CONN_FAILED'
        
        elif isinstance(error, ConfigurationError):
            error_type = ConnectionErrorType.INVALID_CONFIGURATION
            error_code = 'CONFIG_ERROR'
        
        elif isinstance(error, OperationFailure):
            error_type = ConnectionErrorType.INVALID_CONFIGURATION
            error_code = 'OPERATION_ERROR'
        
        elif isinstance(error, NetworkTimeout):
            error_type = ConnectionErrorType.QUERY_TIMEOUT
            error_code = 'NETWORK_TIMEOUT'
        
        elif isinstance(error, (ConnectionRefusedError, OSError)):
            error_type = ConnectionErrorType.CONNECTION_REFUSED
            error_code = 'CONN_REFUSED'
        
        elif isinstance(error, asyncio.TimeoutError):
            error_type = ConnectionErrorType.CONNECTION_TIMEOUT
            error_code = 'CONN_TIMEOUT'
        
        return ConnectionError(
            str(error),
            error_type,
            error_code,
            context={'original_error': error}
        )


# Factory function for easy instantiation
def create_mongodb_connector(config: ConnectionConfig) -> MongoDBConnector:
    """Create MongoDB connector instance"""
    return MongoDBConnector(config)