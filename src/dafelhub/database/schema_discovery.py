"""
Schema Discovery System
Universal schema discovery and analysis supporting multiple database types
"""

import asyncio
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Set, Tuple
from enum import Enum

from dafelhub.core.connections import IDataSourceConnector
from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.database.connectors.connection_factory import DatabaseType


logger = get_logger(__name__)


class ColumnType(Enum):
    """Standard column data types"""
    INTEGER = "integer"
    BIGINT = "bigint"
    SMALLINT = "smallint"
    DECIMAL = "decimal"
    NUMERIC = "numeric"
    REAL = "real"
    DOUBLE = "double"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHAR = "char"
    VARCHAR = "varchar"
    TEXT = "text"
    LONGTEXT = "longtext"
    JSON = "json"
    JSONB = "jsonb"
    XML = "xml"
    DATE = "date"
    TIME = "time"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamptz"
    INTERVAL = "interval"
    BINARY = "binary"
    VARBINARY = "varbinary"
    BLOB = "blob"
    UUID = "uuid"
    ARRAY = "array"
    GEOMETRY = "geometry"
    POINT = "point"
    UNKNOWN = "unknown"


class IndexType(Enum):
    """Database index types"""
    PRIMARY = "primary"
    UNIQUE = "unique"
    INDEX = "index"
    FULLTEXT = "fulltext"
    SPATIAL = "spatial"
    PARTIAL = "partial"
    EXPRESSION = "expression"
    COMPOUND = "compound"


class ConstraintType(Enum):
    """Database constraint types"""
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    UNIQUE = "unique"
    CHECK = "check"
    NOT_NULL = "not_null"
    DEFAULT = "default"


@dataclass
class ColumnInfo:
    """Database column information"""
    name: str
    data_type: ColumnType
    raw_type: str
    nullable: bool = True
    default_value: Optional[str] = None
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None
    auto_increment: bool = False
    comment: Optional[str] = None
    collation: Optional[str] = None
    character_set: Optional[str] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'data_type': self.data_type.value,
            'raw_type': self.raw_type,
            'nullable': self.nullable,
            'default_value': self.default_value,
            'max_length': self.max_length,
            'precision': self.precision,
            'scale': self.scale,
            'auto_increment': self.auto_increment,
            'comment': self.comment,
            'collation': self.collation,
            'character_set': self.character_set,
            'extra_info': self.extra_info
        }


@dataclass
class IndexInfo:
    """Database index information"""
    name: str
    index_type: IndexType
    columns: List[str]
    unique: bool = False
    primary: bool = False
    comment: Optional[str] = None
    size_bytes: Optional[int] = None
    cardinality: Optional[int] = None
    definition: Optional[str] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'index_type': self.index_type.value,
            'columns': self.columns,
            'unique': self.unique,
            'primary': self.primary,
            'comment': self.comment,
            'size_bytes': self.size_bytes,
            'cardinality': self.cardinality,
            'definition': self.definition,
            'extra_info': self.extra_info
        }


@dataclass
class ConstraintInfo:
    """Database constraint information"""
    name: str
    constraint_type: ConstraintType
    columns: List[str]
    referenced_table: Optional[str] = None
    referenced_columns: Optional[List[str]] = None
    definition: Optional[str] = None
    match_option: Optional[str] = None
    update_rule: Optional[str] = None
    delete_rule: Optional[str] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'constraint_type': self.constraint_type.value,
            'columns': self.columns,
            'referenced_table': self.referenced_table,
            'referenced_columns': self.referenced_columns or [],
            'definition': self.definition,
            'match_option': self.match_option,
            'update_rule': self.update_rule,
            'delete_rule': self.delete_rule,
            'extra_info': self.extra_info
        }


@dataclass
class TableInfo:
    """Database table information"""
    name: str
    schema: str
    table_type: str = "BASE TABLE"  # BASE TABLE, VIEW, MATERIALIZED VIEW
    columns: List[ColumnInfo] = field(default_factory=list)
    indexes: List[IndexInfo] = field(default_factory=list)
    constraints: List[ConstraintInfo] = field(default_factory=list)
    row_count: Optional[int] = None
    size_bytes: Optional[int] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    extra_info: Dict[str, Any] = field(default_factory=dict)
    
    def get_column(self, column_name: str) -> Optional[ColumnInfo]:
        """Get column by name"""
        for column in self.columns:
            if column.name == column_name:
                return column
        return None
    
    def get_primary_key_columns(self) -> List[str]:
        """Get primary key column names"""
        pk_columns = []
        for constraint in self.constraints:
            if constraint.constraint_type == ConstraintType.PRIMARY_KEY:
                pk_columns.extend(constraint.columns)
        return pk_columns
    
    def get_foreign_keys(self) -> List[ConstraintInfo]:
        """Get foreign key constraints"""
        return [c for c in self.constraints if c.constraint_type == ConstraintType.FOREIGN_KEY]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'schema': self.schema,
            'table_type': self.table_type,
            'columns': [col.to_dict() for col in self.columns],
            'indexes': [idx.to_dict() for idx in self.indexes],
            'constraints': [cons.to_dict() for cons in self.constraints],
            'row_count': self.row_count,
            'size_bytes': self.size_bytes,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'extra_info': self.extra_info
        }


@dataclass
class DatabaseSchema:
    """Complete database schema information"""
    database_name: str
    schema_name: str
    database_type: DatabaseType
    tables: List[TableInfo] = field(default_factory=list)
    views: List[TableInfo] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    sequences: List[Dict[str, Any]] = field(default_factory=list)
    server_info: Dict[str, Any] = field(default_factory=dict)
    analyzed_at: datetime = field(default_factory=datetime.now)
    analysis_duration: Optional[float] = None
    
    def get_table(self, table_name: str) -> Optional[TableInfo]:
        """Get table by name"""
        for table in self.tables:
            if table.name == table_name:
                return table
        return None
    
    def get_all_tables(self) -> List[TableInfo]:
        """Get all tables and views"""
        return self.tables + self.views
    
    def get_table_relationships(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get foreign key relationships between tables"""
        relationships = {}
        
        for table in self.tables:
            relationships[table.name] = []
            for fk in table.get_foreign_keys():
                if fk.referenced_table:
                    relationships[table.name].append({
                        'type': 'foreign_key',
                        'constraint_name': fk.name,
                        'local_columns': fk.columns,
                        'referenced_table': fk.referenced_table,
                        'referenced_columns': fk.referenced_columns or [],
                        'update_rule': fk.update_rule,
                        'delete_rule': fk.delete_rule
                    })
        
        return relationships
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'database_name': self.database_name,
            'schema_name': self.schema_name,
            'database_type': self.database_type.value,
            'tables': [table.to_dict() for table in self.tables],
            'views': [view.to_dict() for view in self.views],
            'functions': self.functions,
            'procedures': self.procedures,
            'triggers': self.triggers,
            'sequences': self.sequences,
            'server_info': self.server_info,
            'analyzed_at': self.analyzed_at.isoformat(),
            'analysis_duration': self.analysis_duration,
            'summary': {
                'table_count': len(self.tables),
                'view_count': len(self.views),
                'function_count': len(self.functions),
                'procedure_count': len(self.procedures),
                'total_columns': sum(len(table.columns) for table in self.tables),
                'total_indexes': sum(len(table.indexes) for table in self.tables),
                'relationships': self.get_table_relationships()
            }
        }


class SchemaDiscoverer(ABC):
    """Abstract base class for schema discovery"""
    
    @abstractmethod
    async def discover_schema(self, connector: IDataSourceConnector, 
                            schema_name: str = None,
                            include_system_objects: bool = False) -> DatabaseSchema:
        """Discover database schema"""
        pass
    
    @abstractmethod
    def normalize_column_type(self, raw_type: str) -> ColumnType:
        """Normalize database-specific type to standard type"""
        pass


class PostgreSQLSchemaDiscoverer(SchemaDiscoverer):
    """PostgreSQL schema discoverer"""
    
    TYPE_MAPPINGS = {
        'integer': ColumnType.INTEGER,
        'int4': ColumnType.INTEGER,
        'bigint': ColumnType.BIGINT,
        'int8': ColumnType.BIGINT,
        'smallint': ColumnType.SMALLINT,
        'int2': ColumnType.SMALLINT,
        'decimal': ColumnType.DECIMAL,
        'numeric': ColumnType.NUMERIC,
        'real': ColumnType.REAL,
        'float4': ColumnType.REAL,
        'double precision': ColumnType.DOUBLE,
        'float8': ColumnType.DOUBLE,
        'boolean': ColumnType.BOOLEAN,
        'bool': ColumnType.BOOLEAN,
        'character': ColumnType.CHAR,
        'char': ColumnType.CHAR,
        'character varying': ColumnType.VARCHAR,
        'varchar': ColumnType.VARCHAR,
        'text': ColumnType.TEXT,
        'json': ColumnType.JSON,
        'jsonb': ColumnType.JSONB,
        'xml': ColumnType.XML,
        'date': ColumnType.DATE,
        'time': ColumnType.TIME,
        'timestamp': ColumnType.TIMESTAMP,
        'timestamptz': ColumnType.TIMESTAMPTZ,
        'interval': ColumnType.INTERVAL,
        'bytea': ColumnType.BINARY,
        'uuid': ColumnType.UUID,
        'point': ColumnType.POINT,
        'geometry': ColumnType.GEOMETRY
    }
    
    async def discover_schema(self, connector: IDataSourceConnector, 
                            schema_name: str = 'public',
                            include_system_objects: bool = False) -> DatabaseSchema:
        """Discover PostgreSQL schema"""
        start_time = datetime.now()
        
        schema = DatabaseSchema(
            database_name=connector.config.database,
            schema_name=schema_name,
            database_type=DatabaseType.POSTGRESQL
        )
        
        # Get server info
        test_result = await connector.test_connection()
        if test_result.get('success'):
            schema.server_info = test_result.get('server_info', {})
        
        # Discover tables
        tables_query = '''
            SELECT 
                t.table_name,
                t.table_type,
                obj_description(c.oid) as table_comment,
                pg_total_relation_size(c.oid) as size_bytes
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
            LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE t.table_schema = %s
            AND t.table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY t.table_name
        '''
        
        tables_result = await connector.execute_query(tables_query, {'schema': schema_name})
        
        if tables_result.success and tables_result.data:
            for table_row in tables_result.data:
                table_info = TableInfo(
                    name=table_row['table_name'],
                    schema=schema_name,
                    table_type=table_row['table_type'],
                    comment=table_row.get('table_comment'),
                    size_bytes=table_row.get('size_bytes')
                )
                
                # Get columns
                await self._discover_table_columns(connector, table_info, schema_name)
                
                # Get indexes
                await self._discover_table_indexes(connector, table_info, schema_name)
                
                # Get constraints
                await self._discover_table_constraints(connector, table_info, schema_name)
                
                # Get row count estimate
                await self._get_table_row_count(connector, table_info)
                
                if table_info.table_type == 'BASE TABLE':
                    schema.tables.append(table_info)
                else:
                    schema.views.append(table_info)
        
        # Discover functions and procedures
        await self._discover_functions(connector, schema, schema_name)
        
        # Discover sequences
        await self._discover_sequences(connector, schema, schema_name)
        
        # Calculate analysis duration
        schema.analysis_duration = (datetime.now() - start_time).total_seconds()
        
        return schema
    
    async def _discover_table_columns(self, connector: IDataSourceConnector, 
                                    table_info: TableInfo, schema_name: str):
        """Discover table columns"""
        columns_query = '''
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                c.udt_name,
                col_description(pgc.oid, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
            LEFT JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        '''
        
        result = await connector.execute_query(columns_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for col_row in result.data:
                column_type = self.normalize_column_type(col_row['data_type'])
                
                column_info = ColumnInfo(
                    name=col_row['column_name'],
                    data_type=column_type,
                    raw_type=col_row['data_type'],
                    nullable=col_row['is_nullable'] == 'YES',
                    default_value=col_row.get('column_default'),
                    max_length=col_row.get('character_maximum_length'),
                    precision=col_row.get('numeric_precision'),
                    scale=col_row.get('numeric_scale'),
                    comment=col_row.get('column_comment'),
                    auto_increment='nextval(' in (col_row.get('column_default') or ''),
                    extra_info={'udt_name': col_row.get('udt_name')}
                )
                
                table_info.columns.append(column_info)
    
    async def _discover_table_indexes(self, connector: IDataSourceConnector,
                                    table_info: TableInfo, schema_name: str):
        """Discover table indexes"""
        indexes_query = '''
            SELECT 
                i.indexname,
                i.indexdef,
                idx.indisunique as is_unique,
                idx.indisprimary as is_primary,
                obj_description(idx.indexrelid) as comment,
                pg_relation_size(idx.indexrelid) as size_bytes,
                array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as columns
            FROM pg_indexes i
            JOIN pg_class t ON t.relname = i.tablename
            JOIN pg_index idx ON idx.indexrelid = (
                SELECT oid FROM pg_class WHERE relname = i.indexname
            )
            JOIN pg_attribute a ON a.attrelid = idx.indrelid 
                AND a.attnum = ANY(idx.indkey)
            WHERE i.schemaname = %s AND i.tablename = %s
            GROUP BY i.indexname, i.indexdef, idx.indisunique, 
                     idx.indisprimary, idx.indexrelid
        '''
        
        result = await connector.execute_query(indexes_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for idx_row in result.data:
                index_type = IndexType.PRIMARY if idx_row['is_primary'] else \
                           IndexType.UNIQUE if idx_row['is_unique'] else \
                           IndexType.INDEX
                
                index_info = IndexInfo(
                    name=idx_row['indexname'],
                    index_type=index_type,
                    columns=idx_row['columns'] or [],
                    unique=idx_row['is_unique'],
                    primary=idx_row['is_primary'],
                    comment=idx_row.get('comment'),
                    size_bytes=idx_row.get('size_bytes'),
                    definition=idx_row.get('indexdef')
                )
                
                table_info.indexes.append(index_info)
    
    async def _discover_table_constraints(self, connector: IDataSourceConnector,
                                        table_info: TableInfo, schema_name: str):
        """Discover table constraints"""
        constraints_query = '''
            SELECT 
                tc.constraint_name,
                tc.constraint_type,
                array_agg(kcu.column_name ORDER BY kcu.ordinal_position) as columns,
                ccu.table_name as referenced_table,
                array_agg(ccu.column_name ORDER BY kcu.ordinal_position) as referenced_columns,
                rc.match_option,
                rc.update_rule,
                rc.delete_rule,
                cc.check_clause
            FROM information_schema.table_constraints tc
            LEFT JOIN information_schema.key_column_usage kcu ON 
                tc.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu ON 
                tc.constraint_name = ccu.constraint_name
            LEFT JOIN information_schema.referential_constraints rc ON 
                tc.constraint_name = rc.constraint_name
            LEFT JOIN information_schema.check_constraints cc ON 
                tc.constraint_name = cc.constraint_name
            WHERE tc.table_schema = %s AND tc.table_name = %s
            GROUP BY tc.constraint_name, tc.constraint_type, 
                     ccu.table_name, rc.match_option, rc.update_rule, 
                     rc.delete_rule, cc.check_clause
        '''
        
        result = await connector.execute_query(constraints_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for cons_row in result.data:
                constraint_type_map = {
                    'PRIMARY KEY': ConstraintType.PRIMARY_KEY,
                    'FOREIGN KEY': ConstraintType.FOREIGN_KEY,
                    'UNIQUE': ConstraintType.UNIQUE,
                    'CHECK': ConstraintType.CHECK
                }
                
                constraint_type = constraint_type_map.get(
                    cons_row['constraint_type'], 
                    ConstraintType.CHECK
                )
                
                constraint_info = ConstraintInfo(
                    name=cons_row['constraint_name'],
                    constraint_type=constraint_type,
                    columns=cons_row['columns'] or [],
                    referenced_table=cons_row.get('referenced_table'),
                    referenced_columns=cons_row.get('referenced_columns'),
                    match_option=cons_row.get('match_option'),
                    update_rule=cons_row.get('update_rule'),
                    delete_rule=cons_row.get('delete_rule'),
                    definition=cons_row.get('check_clause')
                )
                
                table_info.constraints.append(constraint_info)
    
    async def _get_table_row_count(self, connector: IDataSourceConnector, table_info: TableInfo):
        """Get table row count estimate"""
        try:
            row_count_query = f'''
                SELECT reltuples::bigint as row_count
                FROM pg_class 
                WHERE relname = %s
            '''
            
            result = await connector.execute_query(row_count_query, {'table': table_info.name})
            
            if result.success and result.data and result.data[0]['row_count'] is not None:
                table_info.row_count = int(result.data[0]['row_count'])
        except Exception:
            # Fallback to actual count for small tables
            try:
                count_query = f'SELECT COUNT(*) as row_count FROM "{table_info.name}"'
                result = await connector.execute_query(count_query)
                if result.success and result.data:
                    table_info.row_count = result.data[0]['row_count']
            except Exception:
                pass  # Skip if count fails
    
    async def _discover_functions(self, connector: IDataSourceConnector,
                                schema: DatabaseSchema, schema_name: str):
        """Discover functions and procedures"""
        functions_query = '''
            SELECT 
                routine_name,
                routine_type,
                data_type as return_type,
                routine_definition
            FROM information_schema.routines
            WHERE routine_schema = %s
            ORDER BY routine_name
        '''
        
        result = await connector.execute_query(functions_query, {'schema': schema_name})
        
        if result.success and result.data:
            for func_row in result.data:
                func_info = {
                    'name': func_row['routine_name'],
                    'type': func_row['routine_type'],
                    'return_type': func_row['return_type'],
                    'definition': func_row['routine_definition']
                }
                
                if func_row['routine_type'] == 'FUNCTION':
                    schema.functions.append(func_info)
                else:
                    schema.procedures.append(func_info)
    
    async def _discover_sequences(self, connector: IDataSourceConnector,
                                schema: DatabaseSchema, schema_name: str):
        """Discover sequences"""
        sequences_query = '''
            SELECT 
                sequence_name,
                start_value,
                minimum_value,
                maximum_value,
                increment
            FROM information_schema.sequences
            WHERE sequence_schema = %s
            ORDER BY sequence_name
        '''
        
        result = await connector.execute_query(sequences_query, {'schema': schema_name})
        
        if result.success and result.data:
            for seq_row in result.data:
                seq_info = {
                    'name': seq_row['sequence_name'],
                    'start_value': seq_row['start_value'],
                    'minimum_value': seq_row['minimum_value'],
                    'maximum_value': seq_row['maximum_value'],
                    'increment': seq_row['increment']
                }
                schema.sequences.append(seq_info)
    
    def normalize_column_type(self, raw_type: str) -> ColumnType:
        """Normalize PostgreSQL type to standard type"""
        raw_type_lower = raw_type.lower()
        
        # Handle array types
        if raw_type_lower.endswith('[]'):
            return ColumnType.ARRAY
        
        # Handle parameterized types
        base_type = re.split(r'[(\s]', raw_type_lower)[0]
        
        return self.TYPE_MAPPINGS.get(base_type, ColumnType.UNKNOWN)


class MySQLSchemaDiscoverer(SchemaDiscoverer):
    """MySQL schema discoverer"""
    
    TYPE_MAPPINGS = {
        'int': ColumnType.INTEGER,
        'integer': ColumnType.INTEGER,
        'bigint': ColumnType.BIGINT,
        'smallint': ColumnType.SMALLINT,
        'tinyint': ColumnType.SMALLINT,
        'decimal': ColumnType.DECIMAL,
        'numeric': ColumnType.NUMERIC,
        'float': ColumnType.FLOAT,
        'double': ColumnType.DOUBLE,
        'real': ColumnType.REAL,
        'bit': ColumnType.BOOLEAN,
        'char': ColumnType.CHAR,
        'varchar': ColumnType.VARCHAR,
        'text': ColumnType.TEXT,
        'longtext': ColumnType.LONGTEXT,
        'mediumtext': ColumnType.TEXT,
        'tinytext': ColumnType.TEXT,
        'json': ColumnType.JSON,
        'date': ColumnType.DATE,
        'time': ColumnType.TIME,
        'datetime': ColumnType.TIMESTAMP,
        'timestamp': ColumnType.TIMESTAMP,
        'year': ColumnType.SMALLINT,
        'binary': ColumnType.BINARY,
        'varbinary': ColumnType.VARBINARY,
        'blob': ColumnType.BLOB,
        'longblob': ColumnType.BLOB,
        'mediumblob': ColumnType.BLOB,
        'tinyblob': ColumnType.BLOB,
        'geometry': ColumnType.GEOMETRY,
        'point': ColumnType.POINT
    }
    
    async def discover_schema(self, connector: IDataSourceConnector, 
                            schema_name: str = None,
                            include_system_objects: bool = False) -> DatabaseSchema:
        """Discover MySQL schema"""
        start_time = datetime.now()
        
        if not schema_name:
            schema_name = connector.config.database
        
        schema = DatabaseSchema(
            database_name=connector.config.database,
            schema_name=schema_name,
            database_type=DatabaseType.MYSQL
        )
        
        # Get server info
        test_result = await connector.test_connection()
        if test_result.get('success'):
            schema.server_info = test_result.get('server_info', {})
        
        # Discover tables
        tables_query = '''
            SELECT 
                table_name,
                table_type,
                table_comment,
                table_rows,
                data_length,
                index_length,
                auto_increment,
                create_time,
                update_time
            FROM information_schema.tables
            WHERE table_schema = %s
            AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
        '''
        
        tables_result = await connector.execute_query(tables_query, {'schema': schema_name})
        
        if tables_result.success and tables_result.data:
            for table_row in tables_result.data:
                table_info = TableInfo(
                    name=table_row['table_name'],
                    schema=schema_name,
                    table_type=table_row['table_type'],
                    comment=table_row.get('table_comment'),
                    row_count=table_row.get('table_rows'),
                    size_bytes=table_row.get('data_length'),
                    created_at=table_row.get('create_time'),
                    updated_at=table_row.get('update_time'),
                    extra_info={
                        'index_length': table_row.get('index_length'),
                        'auto_increment': table_row.get('auto_increment')
                    }
                )
                
                # Get columns
                await self._discover_table_columns(connector, table_info, schema_name)
                
                # Get indexes
                await self._discover_table_indexes(connector, table_info, schema_name)
                
                # Get constraints
                await self._discover_table_constraints(connector, table_info, schema_name)
                
                if table_info.table_type == 'BASE TABLE':
                    schema.tables.append(table_info)
                else:
                    schema.views.append(table_info)
        
        # Discover stored procedures and functions
        await self._discover_routines(connector, schema, schema_name)
        
        # Calculate analysis duration
        schema.analysis_duration = (datetime.now() - start_time).total_seconds()
        
        return schema
    
    async def _discover_table_columns(self, connector: IDataSourceConnector, 
                                    table_info: TableInfo, schema_name: str):
        """Discover MySQL table columns"""
        columns_query = '''
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                column_comment,
                column_key,
                extra,
                character_set_name,
                collation_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        '''
        
        result = await connector.execute_query(columns_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for col_row in result.data:
                column_type = self.normalize_column_type(col_row['data_type'])
                
                column_info = ColumnInfo(
                    name=col_row['column_name'],
                    data_type=column_type,
                    raw_type=col_row['data_type'],
                    nullable=col_row['is_nullable'] == 'YES',
                    default_value=col_row.get('column_default'),
                    max_length=col_row.get('character_maximum_length'),
                    precision=col_row.get('numeric_precision'),
                    scale=col_row.get('numeric_scale'),
                    comment=col_row.get('column_comment'),
                    auto_increment='auto_increment' in (col_row.get('extra') or ''),
                    character_set=col_row.get('character_set_name'),
                    collation=col_row.get('collation_name'),
                    extra_info={
                        'column_key': col_row.get('column_key'),
                        'extra': col_row.get('extra')
                    }
                )
                
                table_info.columns.append(column_info)
    
    async def _discover_table_indexes(self, connector: IDataSourceConnector,
                                    table_info: TableInfo, schema_name: str):
        """Discover MySQL table indexes"""
        indexes_query = '''
            SELECT DISTINCT
                index_name,
                non_unique,
                index_type,
                index_comment,
                GROUP_CONCAT(column_name ORDER BY seq_in_index) as columns,
                cardinality
            FROM information_schema.statistics
            WHERE table_schema = %s AND table_name = %s
            GROUP BY index_name, non_unique, index_type, index_comment, cardinality
            ORDER BY index_name
        '''
        
        result = await connector.execute_query(indexes_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for idx_row in result.data:
                is_primary = idx_row['index_name'] == 'PRIMARY'
                is_unique = idx_row['non_unique'] == 0
                
                index_type = IndexType.PRIMARY if is_primary else \
                           IndexType.UNIQUE if is_unique else \
                           IndexType.FULLTEXT if idx_row['index_type'] == 'FULLTEXT' else \
                           IndexType.SPATIAL if idx_row['index_type'] == 'SPATIAL' else \
                           IndexType.INDEX
                
                columns = idx_row['columns'].split(',') if idx_row['columns'] else []
                
                index_info = IndexInfo(
                    name=idx_row['index_name'],
                    index_type=index_type,
                    columns=columns,
                    unique=is_unique,
                    primary=is_primary,
                    comment=idx_row.get('index_comment'),
                    cardinality=idx_row.get('cardinality'),
                    extra_info={'index_type': idx_row.get('index_type')}
                )
                
                table_info.indexes.append(index_info)
    
    async def _discover_table_constraints(self, connector: IDataSourceConnector,
                                        table_info: TableInfo, schema_name: str):
        """Discover MySQL table constraints"""
        # Foreign key constraints
        fk_query = '''
            SELECT 
                constraint_name,
                GROUP_CONCAT(column_name ORDER BY ordinal_position) as columns,
                referenced_table_name,
                GROUP_CONCAT(referenced_column_name ORDER BY ordinal_position) as referenced_columns,
                update_rule,
                delete_rule,
                match_option
            FROM information_schema.key_column_usage
            WHERE table_schema = %s AND table_name = %s
            AND referenced_table_name IS NOT NULL
            GROUP BY constraint_name, referenced_table_name, update_rule, delete_rule, match_option
        '''
        
        result = await connector.execute_query(fk_query, {
            'schema': schema_name,
            'table': table_info.name
        })
        
        if result.success and result.data:
            for fk_row in result.data:
                columns = fk_row['columns'].split(',') if fk_row['columns'] else []
                ref_columns = fk_row['referenced_columns'].split(',') if fk_row['referenced_columns'] else []
                
                constraint_info = ConstraintInfo(
                    name=fk_row['constraint_name'],
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    columns=columns,
                    referenced_table=fk_row['referenced_table_name'],
                    referenced_columns=ref_columns,
                    update_rule=fk_row.get('update_rule'),
                    delete_rule=fk_row.get('delete_rule'),
                    match_option=fk_row.get('match_option')
                )
                
                table_info.constraints.append(constraint_info)
        
        # Check constraints (MySQL 8.0+)
        check_query = '''
            SELECT 
                constraint_name,
                check_clause
            FROM information_schema.check_constraints
            WHERE constraint_schema = %s 
            AND table_name = %s
        '''
        
        try:
            result = await connector.execute_query(check_query, {
                'schema': schema_name,
                'table': table_info.name
            })
            
            if result.success and result.data:
                for check_row in result.data:
                    constraint_info = ConstraintInfo(
                        name=check_row['constraint_name'],
                        constraint_type=ConstraintType.CHECK,
                        columns=[],  # Would need to parse check clause to extract columns
                        definition=check_row.get('check_clause')
                    )
                    
                    table_info.constraints.append(constraint_info)
        except Exception:
            pass  # CHECK constraints not supported in older MySQL versions
    
    async def _discover_routines(self, connector: IDataSourceConnector,
                               schema: DatabaseSchema, schema_name: str):
        """Discover MySQL stored procedures and functions"""
        routines_query = '''
            SELECT 
                routine_name,
                routine_type,
                data_type,
                routine_definition
            FROM information_schema.routines
            WHERE routine_schema = %s
            ORDER BY routine_name
        '''
        
        result = await connector.execute_query(routines_query, {'schema': schema_name})
        
        if result.success and result.data:
            for routine_row in result.data:
                routine_info = {
                    'name': routine_row['routine_name'],
                    'type': routine_row['routine_type'],
                    'return_type': routine_row['data_type'],
                    'definition': routine_row['routine_definition']
                }
                
                if routine_row['routine_type'] == 'FUNCTION':
                    schema.functions.append(routine_info)
                else:
                    schema.procedures.append(routine_info)
    
    def normalize_column_type(self, raw_type: str) -> ColumnType:
        """Normalize MySQL type to standard type"""
        raw_type_lower = raw_type.lower()
        
        # Handle tinyint(1) as boolean
        if raw_type_lower == 'tinyint' or 'tinyint(1)' in raw_type_lower:
            return ColumnType.BOOLEAN
        
        # Handle unsigned integers
        if 'unsigned' in raw_type_lower:
            if 'bigint' in raw_type_lower:
                return ColumnType.BIGINT
            elif 'int' in raw_type_lower:
                return ColumnType.INTEGER
            elif 'smallint' in raw_type_lower or 'tinyint' in raw_type_lower:
                return ColumnType.SMALLINT
        
        # Handle parameterized types
        base_type = re.split(r'[(\s]', raw_type_lower)[0]
        
        return self.TYPE_MAPPINGS.get(base_type, ColumnType.UNKNOWN)


class MongoDBSchemaDiscoverer(SchemaDiscoverer):
    """MongoDB schema discoverer"""
    
    async def discover_schema(self, connector: IDataSourceConnector, 
                            schema_name: str = None,
                            include_system_objects: bool = False) -> DatabaseSchema:
        """Discover MongoDB schema"""
        start_time = datetime.now()
        
        schema = DatabaseSchema(
            database_name=connector.config.database,
            schema_name=schema_name or connector.config.database,
            database_type=DatabaseType.MONGODB
        )
        
        # Get server info
        test_result = await connector.test_connection()
        if test_result.get('success'):
            schema.server_info = test_result.get('server_info', {})
        
        # Get schema info from connector
        schema_info = await connector.get_schema_info()
        
        if schema_info.get('collections'):
            for collection_data in schema_info['collections']:
                table_info = TableInfo(
                    name=collection_data['name'],
                    schema=schema.schema_name,
                    table_type='COLLECTION',
                    row_count=collection_data.get('count', 0),
                    size_bytes=collection_data.get('size', 0),
                    extra_info={
                        'storage_size': collection_data.get('storage_size', 0),
                        'avg_obj_size': collection_data.get('avg_obj_size', 0),
                        'capped': collection_data.get('capped', False),
                        'max_documents': collection_data.get('max'),
                        'inferred_schema': collection_data.get('inferred_schema', {})
                    }
                )
                
                # Convert inferred schema to columns
                if collection_data.get('inferred_schema'):
                    for field_name, field_info in collection_data['inferred_schema'].items():
                        column_type = self._infer_column_type_from_mongo(field_info.get('types', []))
                        
                        column_info = ColumnInfo(
                            name=field_name,
                            data_type=column_type,
                            raw_type=', '.join(field_info.get('types', [])),
                            nullable=field_info.get('nullable', False),
                            extra_info={
                                'example': field_info.get('example'),
                                'types': field_info.get('types', [])
                            }
                        )
                        
                        table_info.columns.append(column_info)
                
                # Convert indexes
                if collection_data.get('indexes'):
                    for index_data in collection_data['indexes']:
                        index_type = IndexType.PRIMARY if index_data.get('name') == '_id_' else \
                                   IndexType.UNIQUE if index_data.get('unique') else \
                                   IndexType.INDEX
                        
                        # Extract column names from MongoDB index key
                        columns = list(index_data.get('key', {}).keys()) if index_data.get('key') else []
                        
                        index_info = IndexInfo(
                            name=index_data['name'],
                            index_type=index_type,
                            columns=columns,
                            unique=index_data.get('unique', False),
                            primary=index_data.get('name') == '_id_',
                            extra_info={
                                'key': index_data.get('key'),
                                'sparse': index_data.get('sparse', False),
                                'background': index_data.get('background', False)
                            }
                        )
                        
                        table_info.indexes.append(index_info)
                
                schema.tables.append(table_info)
        
        # Calculate analysis duration
        schema.analysis_duration = (datetime.now() - start_time).total_seconds()
        
        return schema
    
    def _infer_column_type_from_mongo(self, type_names: List[str]) -> ColumnType:
        """Infer column type from MongoDB type names"""
        if not type_names:
            return ColumnType.UNKNOWN
        
        # MongoDB type mappings
        type_mapping = {
            'int': ColumnType.INTEGER,
            'long': ColumnType.BIGINT,
            'float': ColumnType.FLOAT,
            'double': ColumnType.DOUBLE,
            'bool': ColumnType.BOOLEAN,
            'str': ColumnType.VARCHAR,
            'datetime': ColumnType.TIMESTAMP,
            'date': ColumnType.DATE,
            'ObjectId': ColumnType.VARCHAR,
            'list': ColumnType.ARRAY,
            'dict': ColumnType.JSON,
            'NoneType': ColumnType.UNKNOWN
        }
        
        # Use the first recognized type
        for type_name in type_names:
            if type_name in type_mapping:
                return type_mapping[type_name]
        
        return ColumnType.UNKNOWN
    
    def normalize_column_type(self, raw_type: str) -> ColumnType:
        """Normalize MongoDB type to standard type"""
        return self._infer_column_type_from_mongo([raw_type])


class UniversalSchemaDiscoverer(LoggerMixin):
    """
    Universal schema discoverer supporting multiple database types
    """
    
    def __init__(self):
        self._discoverers = {
            DatabaseType.POSTGRESQL: PostgreSQLSchemaDiscoverer(),
            DatabaseType.MYSQL: MySQLSchemaDiscoverer(),
            DatabaseType.MONGODB: MongoDBSchemaDiscoverer()
        }
        
        self.logger.info("Universal schema discoverer initialized")
    
    def register_discoverer(self, database_type: DatabaseType, 
                          discoverer: SchemaDiscoverer) -> None:
        """Register a custom schema discoverer"""
        self._discoverers[database_type] = discoverer
        self.logger.info(f"Registered schema discoverer for {database_type.value}")
    
    async def discover_schema(self, connector: IDataSourceConnector, 
                            database_type: DatabaseType,
                            schema_name: str = None,
                            include_system_objects: bool = False) -> DatabaseSchema:
        """Discover schema using appropriate discoverer"""
        if database_type not in self._discoverers:
            raise ValueError(f"No schema discoverer available for {database_type.value}")
        
        discoverer = self._discoverers[database_type]
        
        self.logger.info(f"Starting schema discovery for {database_type.value}", 
                        extra_data={
                            "database": connector.config.database,
                            "schema": schema_name,
                            "include_system": include_system_objects
                        })
        
        try:
            schema = await discoverer.discover_schema(
                connector, schema_name, include_system_objects
            )
            
            self.logger.info(f"Schema discovery completed for {database_type.value}",
                           extra_data={
                               "tables": len(schema.tables),
                               "views": len(schema.views),
                               "functions": len(schema.functions),
                               "duration": schema.analysis_duration
                           })
            
            return schema
            
        except Exception as e:
            self.logger.error(f"Schema discovery failed for {database_type.value}",
                            extra_data={"error": str(e)})
            raise
    
    async def compare_schemas(self, schema1: DatabaseSchema, 
                            schema2: DatabaseSchema) -> Dict[str, Any]:
        """Compare two database schemas"""
        comparison = {
            'schema1': {
                'database': schema1.database_name,
                'type': schema1.database_type.value,
                'tables': len(schema1.tables),
                'views': len(schema1.views)
            },
            'schema2': {
                'database': schema2.database_name,
                'type': schema2.database_type.value,
                'tables': len(schema2.tables),
                'views': len(schema2.views)
            },
            'differences': {
                'tables_only_in_schema1': [],
                'tables_only_in_schema2': [],
                'tables_with_differences': [],
                'column_differences': {}
            }
        }
        
        schema1_tables = {t.name: t for t in schema1.tables}
        schema2_tables = {t.name: t for t in schema2.tables}
        
        # Find tables that exist only in one schema
        comparison['differences']['tables_only_in_schema1'] = [
            name for name in schema1_tables.keys() if name not in schema2_tables
        ]
        comparison['differences']['tables_only_in_schema2'] = [
            name for name in schema2_tables.keys() if name not in schema1_tables
        ]
        
        # Compare common tables
        common_tables = set(schema1_tables.keys()) & set(schema2_tables.keys())
        
        for table_name in common_tables:
            table1 = schema1_tables[table_name]
            table2 = schema2_tables[table_name]
            
            table_diff = self._compare_tables(table1, table2)
            if table_diff['has_differences']:
                comparison['differences']['tables_with_differences'].append(table_name)
                comparison['differences']['column_differences'][table_name] = table_diff
        
        return comparison
    
    def _compare_tables(self, table1: TableInfo, table2: TableInfo) -> Dict[str, Any]:
        """Compare two table structures"""
        table1_columns = {c.name: c for c in table1.columns}
        table2_columns = {c.name: c for c in table2.columns}
        
        differences = {
            'has_differences': False,
            'columns_only_in_table1': [],
            'columns_only_in_table2': [],
            'columns_with_type_differences': [],
            'columns_with_constraint_differences': []
        }
        
        # Find columns that exist only in one table
        differences['columns_only_in_table1'] = [
            name for name in table1_columns.keys() if name not in table2_columns
        ]
        differences['columns_only_in_table2'] = [
            name for name in table2_columns.keys() if name not in table1_columns
        ]
        
        # Compare common columns
        common_columns = set(table1_columns.keys()) & set(table2_columns.keys())
        
        for column_name in common_columns:
            col1 = table1_columns[column_name]
            col2 = table2_columns[column_name]
            
            if col1.data_type != col2.data_type or col1.nullable != col2.nullable:
                differences['columns_with_type_differences'].append({
                    'column': column_name,
                    'table1_type': col1.data_type.value,
                    'table2_type': col2.data_type.value,
                    'table1_nullable': col1.nullable,
                    'table2_nullable': col2.nullable
                })
        
        # Check if there are any differences
        differences['has_differences'] = any([
            differences['columns_only_in_table1'],
            differences['columns_only_in_table2'],
            differences['columns_with_type_differences'],
            differences['columns_with_constraint_differences']
        ])
        
        return differences
    
    def get_supported_databases(self) -> List[DatabaseType]:
        """Get list of supported database types"""
        return list(self._discoverers.keys())


# Global discoverer instance
schema_discoverer = UniversalSchemaDiscoverer()


# Convenience functions
async def discover_schema(connector: IDataSourceConnector, 
                        database_type: DatabaseType,
                        schema_name: str = None,
                        include_system_objects: bool = False) -> DatabaseSchema:
    """Discover schema using global discoverer"""
    return await schema_discoverer.discover_schema(
        connector, database_type, schema_name, include_system_objects
    )


async def compare_schemas(schema1: DatabaseSchema, schema2: DatabaseSchema) -> Dict[str, Any]:
    """Compare schemas using global discoverer"""
    return await schema_discoverer.compare_schemas(schema1, schema2)