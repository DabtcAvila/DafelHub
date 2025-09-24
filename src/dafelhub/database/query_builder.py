"""
Query Builder System
Universal query builder supporting multiple database types with SQL generation and optimization
"""

import re
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union, Tuple, Set
from enum import Enum

from dafelhub.core.logging import get_logger, LoggerMixin
from dafelhub.database.connectors.connection_factory import DatabaseType


logger = get_logger(__name__)


class QueryType(Enum):
    """Query operation types"""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE_TABLE = "CREATE_TABLE"
    ALTER_TABLE = "ALTER_TABLE"
    DROP_TABLE = "DROP_TABLE"
    CREATE_INDEX = "CREATE_INDEX"
    DROP_INDEX = "DROP_INDEX"


class JoinType(Enum):
    """SQL JOIN types"""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class OrderDirection(Enum):
    """ORDER BY directions"""
    ASC = "ASC"
    DESC = "DESC"


class ComparisonOperator(Enum):
    """Comparison operators"""
    EQUALS = "="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_EQUAL = "<="
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"


@dataclass
class QueryCondition:
    """Represents a query condition/predicate"""
    column: str
    operator: ComparisonOperator
    value: Any = None
    table_alias: Optional[str] = None
    
    def to_sql(self, db_type: DatabaseType) -> Tuple[str, List[Any]]:
        """Convert condition to SQL with parameters"""
        column_ref = f"{self.table_alias}.{self.column}" if self.table_alias else self.column
        
        if self.operator in [ComparisonOperator.IS_NULL, ComparisonOperator.IS_NOT_NULL]:
            return f"{column_ref} {self.operator.value}", []
        
        elif self.operator in [ComparisonOperator.IN, ComparisonOperator.NOT_IN]:
            if isinstance(self.value, (list, tuple)):
                placeholders = ', '.join(['%s'] * len(self.value))
                return f"{column_ref} {self.operator.value} ({placeholders})", list(self.value)
            else:
                return f"{column_ref} {self.operator.value} (%s)", [self.value]
        
        elif self.operator in [ComparisonOperator.BETWEEN, ComparisonOperator.NOT_BETWEEN]:
            if isinstance(self.value, (list, tuple)) and len(self.value) == 2:
                return f"{column_ref} {self.operator.value} %s AND %s", list(self.value)
            else:
                raise ValueError(f"BETWEEN operator requires a list/tuple of 2 values, got: {self.value}")
        
        else:
            # Handle ILIKE for databases that don't support it
            operator = self.operator.value
            if self.operator == ComparisonOperator.ILIKE and db_type == DatabaseType.MYSQL:
                operator = "LIKE"
                # Convert value to lowercase for case-insensitive comparison
                if isinstance(self.value, str):
                    column_ref = f"LOWER({column_ref})"
                    value = self.value.lower()
                else:
                    value = self.value
                return f"{column_ref} {operator} %s", [value]
            
            return f"{column_ref} {operator} %s", [self.value]


@dataclass
class QueryJoin:
    """Represents a table join"""
    table: str
    alias: Optional[str] = None
    join_type: JoinType = JoinType.INNER
    conditions: List[QueryCondition] = field(default_factory=list)
    on_clause: Optional[str] = None
    
    def to_sql(self, db_type: DatabaseType) -> Tuple[str, List[Any]]:
        """Convert join to SQL"""
        table_ref = f"{self.table} AS {self.alias}" if self.alias else self.table
        join_sql = f"{self.join_type.value} {table_ref}"
        
        params = []
        
        if self.on_clause:
            join_sql += f" ON {self.on_clause}"
        elif self.conditions:
            condition_parts = []
            for condition in self.conditions:
                cond_sql, cond_params = condition.to_sql(db_type)
                condition_parts.append(cond_sql)
                params.extend(cond_params)
            join_sql += f" ON {' AND '.join(condition_parts)}"
        
        return join_sql, params


@dataclass
class QueryOrderBy:
    """Represents ORDER BY clause"""
    column: str
    direction: OrderDirection = OrderDirection.ASC
    table_alias: Optional[str] = None
    
    def to_sql(self) -> str:
        """Convert to SQL"""
        column_ref = f"{self.table_alias}.{self.column}" if self.table_alias else self.column
        return f"{column_ref} {self.direction.value}"


@dataclass
class QueryGroupBy:
    """Represents GROUP BY clause"""
    columns: List[str] = field(default_factory=list)
    having_conditions: List[QueryCondition] = field(default_factory=list)
    
    def to_sql(self, db_type: DatabaseType) -> Tuple[str, List[Any]]:
        """Convert to SQL"""
        if not self.columns:
            return "", []
        
        group_sql = f"GROUP BY {', '.join(self.columns)}"
        params = []
        
        if self.having_conditions:
            having_parts = []
            for condition in self.having_conditions:
                cond_sql, cond_params = condition.to_sql(db_type)
                having_parts.append(cond_sql)
                params.extend(cond_params)
            group_sql += f" HAVING {' AND '.join(having_parts)}"
        
        return group_sql, params


class SQLDialect(ABC):
    """Abstract base class for SQL dialects"""
    
    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Quote database identifier"""
        pass
    
    @abstractmethod
    def get_limit_clause(self, limit: int, offset: int = None) -> str:
        """Get LIMIT clause for pagination"""
        pass
    
    @abstractmethod
    def get_date_format_function(self, column: str, format_string: str) -> str:
        """Get date formatting function"""
        pass
    
    @abstractmethod
    def get_string_concat_operator(self) -> str:
        """Get string concatenation operator"""
        pass
    
    @abstractmethod
    def supports_boolean_type(self) -> bool:
        """Check if database supports boolean data type"""
        pass
    
    @abstractmethod
    def get_auto_increment_syntax(self) -> str:
        """Get auto increment syntax"""
        pass


class PostgreSQLDialect(SQLDialect):
    """PostgreSQL SQL dialect"""
    
    def quote_identifier(self, identifier: str) -> str:
        return f'"{identifier}"'
    
    def get_limit_clause(self, limit: int, offset: int = None) -> str:
        if offset:
            return f"LIMIT {limit} OFFSET {offset}"
        return f"LIMIT {limit}"
    
    def get_date_format_function(self, column: str, format_string: str) -> str:
        return f"TO_CHAR({column}, '{format_string}')"
    
    def get_string_concat_operator(self) -> str:
        return "||"
    
    def supports_boolean_type(self) -> bool:
        return True
    
    def get_auto_increment_syntax(self) -> str:
        return "SERIAL"


class MySQLDialect(SQLDialect):
    """MySQL SQL dialect"""
    
    def quote_identifier(self, identifier: str) -> str:
        return f"`{identifier}`"
    
    def get_limit_clause(self, limit: int, offset: int = None) -> str:
        if offset:
            return f"LIMIT {offset}, {limit}"
        return f"LIMIT {limit}"
    
    def get_date_format_function(self, column: str, format_string: str) -> str:
        return f"DATE_FORMAT({column}, '{format_string}')"
    
    def get_string_concat_operator(self) -> str:
        return "CONCAT"
    
    def supports_boolean_type(self) -> bool:
        return False  # MySQL uses TINYINT(1)
    
    def get_auto_increment_syntax(self) -> str:
        return "AUTO_INCREMENT"


class MongoQueryBuilder:
    """MongoDB query builder for NoSQL operations"""
    
    def __init__(self):
        self.collection = None
        self.filter_conditions = {}
        self.projection_fields = None
        self.sort_specification = None
        self.limit_count = None
        self.skip_count = None
        self.aggregation_pipeline = []
    
    def from_collection(self, collection: str) -> 'MongoQueryBuilder':
        """Set target collection"""
        self.collection = collection
        return self
    
    def where(self, field: str, operator: str, value: Any) -> 'MongoQueryBuilder':
        """Add filter condition"""
        mongo_operators = {
            '=': '$eq',
            '!=': '$ne',
            '>': '$gt',
            '>=': '$gte',
            '<': '$lt',
            '<=': '$lte',
            'in': '$in',
            'not_in': '$nin',
            'regex': '$regex',
            'exists': '$exists'
        }
        
        if operator in mongo_operators:
            self.filter_conditions[field] = {mongo_operators[operator]: value}
        elif operator == 'between':
            if isinstance(value, (list, tuple)) and len(value) == 2:
                self.filter_conditions[field] = {'$gte': value[0], '$lte': value[1]}
        
        return self
    
    def select(self, *fields: str) -> 'MongoQueryBuilder':
        """Set projection fields"""
        if fields:
            self.projection_fields = {field: 1 for field in fields}
        return self
    
    def order_by(self, field: str, direction: str = 'asc') -> 'MongoQueryBuilder':
        """Add sort specification"""
        if not self.sort_specification:
            self.sort_specification = {}
        self.sort_specification[field] = 1 if direction.lower() == 'asc' else -1
        return self
    
    def limit(self, count: int) -> 'MongoQueryBuilder':
        """Set limit"""
        self.limit_count = count
        return self
    
    def skip(self, count: int) -> 'MongoQueryBuilder':
        """Set skip (offset)"""
        self.skip_count = count
        return self
    
    def aggregate(self, *stages: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add aggregation stages"""
        self.aggregation_pipeline.extend(stages)
        return self
    
    def match(self, conditions: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add $match stage to aggregation"""
        self.aggregation_pipeline.append({'$match': conditions})
        return self
    
    def group(self, group_spec: Dict[str, Any]) -> 'MongoQueryBuilder':
        """Add $group stage to aggregation"""
        self.aggregation_pipeline.append({'$group': group_spec})
        return self
    
    def lookup(self, from_collection: str, local_field: str, 
              foreign_field: str, as_field: str) -> 'MongoQueryBuilder':
        """Add $lookup stage (join equivalent)"""
        self.aggregation_pipeline.append({
            '$lookup': {
                'from': from_collection,
                'localField': local_field,
                'foreignField': foreign_field,
                'as': as_field
            }
        })
        return self
    
    def build_find_query(self) -> Dict[str, Any]:
        """Build find query"""
        query = {
            'collection': self.collection,
            'filter': self.filter_conditions
        }
        
        if self.projection_fields:
            query['projection'] = self.projection_fields
        if self.sort_specification:
            query['sort'] = self.sort_specification
        if self.limit_count:
            query['limit'] = self.limit_count
        if self.skip_count:
            query['skip'] = self.skip_count
        
        return query
    
    def build_aggregation(self) -> Dict[str, Any]:
        """Build aggregation query"""
        if self.filter_conditions and not any('$match' in stage for stage in self.aggregation_pipeline):
            # Add match stage at the beginning if not present
            self.aggregation_pipeline.insert(0, {'$match': self.filter_conditions})
        
        return {
            'collection': self.collection,
            'pipeline': self.aggregation_pipeline
        }
    
    def build_insert(self, documents: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Build insert query"""
        if not isinstance(documents, list):
            documents = [documents]
        
        return {
            'collection': self.collection,
            'documents': documents
        }
    
    def build_update(self, update_doc: Dict[str, Any], upsert: bool = False, 
                    multi: bool = False) -> Dict[str, Any]:
        """Build update query"""
        return {
            'collection': self.collection,
            'filter': self.filter_conditions,
            'update': update_doc,
            'upsert': upsert,
            'multi': multi
        }
    
    def build_delete(self, multi: bool = False) -> Dict[str, Any]:
        """Build delete query"""
        return {
            'collection': self.collection,
            'filter': self.filter_conditions,
            'multi': multi
        }


class UniversalQueryBuilder(LoggerMixin):
    """
    Universal query builder supporting multiple database types:
    - SQL databases (PostgreSQL, MySQL, SQLite, etc.)
    - NoSQL databases (MongoDB)
    - Query optimization and validation
    - Cross-database query translation
    """
    
    def __init__(self, database_type: DatabaseType = DatabaseType.POSTGRESQL):
        self.database_type = database_type
        self.dialect = self._get_dialect()
        
        # Query components
        self.query_type: Optional[QueryType] = None
        self.select_columns: List[str] = []
        self.from_table: Optional[str] = None
        self.table_alias: Optional[str] = None
        self.joins: List[QueryJoin] = []
        self.where_conditions: List[QueryCondition] = []
        self.group_by: Optional[QueryGroupBy] = None
        self.order_by: List[QueryOrderBy] = []
        self.limit_count: Optional[int] = None
        self.offset_count: Optional[int] = None
        
        # INSERT/UPDATE specific
        self.insert_columns: List[str] = []
        self.insert_values: List[Any] = []
        self.update_assignments: Dict[str, Any] = {}
        
        # MongoDB query builder
        self.mongo_builder: Optional[MongoQueryBuilder] = None
        if database_type == DatabaseType.MONGODB:
            self.mongo_builder = MongoQueryBuilder()
        
        self.logger.debug(f"Query builder initialized for {database_type.value}")
    
    def _get_dialect(self) -> SQLDialect:
        """Get SQL dialect for database type"""
        if self.database_type == DatabaseType.POSTGRESQL:
            return PostgreSQLDialect()
        elif self.database_type == DatabaseType.MYSQL:
            return MySQLDialect()
        else:
            # Default to PostgreSQL dialect
            return PostgreSQLDialect()
    
    # Fluent interface methods
    
    def select(self, *columns: str) -> 'UniversalQueryBuilder':
        """Add SELECT columns"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.select(*columns)
            return self
        
        self.query_type = QueryType.SELECT
        if columns:
            self.select_columns.extend(columns)
        else:
            self.select_columns = ['*']
        return self
    
    def from_table(self, table: str, alias: str = None) -> 'UniversalQueryBuilder':
        """Set FROM table"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.from_collection(table)
            return self
        
        self.from_table = table
        self.table_alias = alias
        return self
    
    def join(self, table: str, alias: str = None, join_type: JoinType = JoinType.INNER) -> 'UniversalQueryBuilder':
        """Add JOIN clause"""
        if self.database_type == DatabaseType.MONGODB:
            # MongoDB doesn't have traditional joins, but we can use $lookup in aggregation
            return self
        
        join_obj = QueryJoin(table=table, alias=alias, join_type=join_type)
        self.joins.append(join_obj)
        return self
    
    def on(self, left_column: str, right_column: str, left_alias: str = None, 
           right_alias: str = None) -> 'UniversalQueryBuilder':
        """Add JOIN ON condition to the last join"""
        if self.database_type == DatabaseType.MONGODB or not self.joins:
            return self
        
        left_ref = f"{left_alias}.{left_column}" if left_alias else left_column
        right_ref = f"{right_alias}.{right_column}" if right_alias else right_column
        
        self.joins[-1].on_clause = f"{left_ref} = {right_ref}"
        return self
    
    def where(self, column: str, operator: Union[ComparisonOperator, str], 
              value: Any = None, table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add WHERE condition"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                op_str = operator.value if isinstance(operator, ComparisonOperator) else operator
                self.mongo_builder.where(column, op_str.lower().replace(' ', '_'), value)
            return self
        
        if isinstance(operator, str):
            # Try to convert string to ComparisonOperator
            op_map = {
                '=': ComparisonOperator.EQUALS,
                '!=': ComparisonOperator.NOT_EQUALS,
                '<>': ComparisonOperator.NOT_EQUALS,
                '>': ComparisonOperator.GREATER_THAN,
                '>=': ComparisonOperator.GREATER_THAN_EQUAL,
                '<': ComparisonOperator.LESS_THAN,
                '<=': ComparisonOperator.LESS_THAN_EQUAL,
                'like': ComparisonOperator.LIKE,
                'ilike': ComparisonOperator.ILIKE,
                'in': ComparisonOperator.IN,
                'not in': ComparisonOperator.NOT_IN,
                'is null': ComparisonOperator.IS_NULL,
                'is not null': ComparisonOperator.IS_NOT_NULL,
                'between': ComparisonOperator.BETWEEN
            }
            operator = op_map.get(operator.lower(), ComparisonOperator.EQUALS)
        
        condition = QueryCondition(
            column=column,
            operator=operator,
            value=value,
            table_alias=table_alias
        )
        self.where_conditions.append(condition)
        return self
    
    def where_in(self, column: str, values: List[Any], 
                table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add WHERE IN condition"""
        return self.where(column, ComparisonOperator.IN, values, table_alias)
    
    def where_between(self, column: str, start_value: Any, end_value: Any,
                     table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add WHERE BETWEEN condition"""
        return self.where(column, ComparisonOperator.BETWEEN, [start_value, end_value], table_alias)
    
    def where_like(self, column: str, pattern: str, 
                  case_sensitive: bool = True, table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add WHERE LIKE condition"""
        operator = ComparisonOperator.LIKE if case_sensitive else ComparisonOperator.ILIKE
        return self.where(column, operator, pattern, table_alias)
    
    def where_null(self, column: str, is_null: bool = True, 
                  table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add WHERE NULL condition"""
        operator = ComparisonOperator.IS_NULL if is_null else ComparisonOperator.IS_NOT_NULL
        return self.where(column, operator, None, table_alias)
    
    def group_by_columns(self, *columns: str) -> 'UniversalQueryBuilder':
        """Add GROUP BY clause"""
        if self.database_type == DatabaseType.MONGODB:
            # MongoDB grouping is done through aggregation pipeline
            return self
        
        if not self.group_by:
            self.group_by = QueryGroupBy()
        self.group_by.columns.extend(columns)
        return self
    
    def having(self, column: str, operator: Union[ComparisonOperator, str], 
              value: Any = None) -> 'UniversalQueryBuilder':
        """Add HAVING condition"""
        if self.database_type == DatabaseType.MONGODB:
            return self
        
        if not self.group_by:
            self.group_by = QueryGroupBy()
        
        if isinstance(operator, str):
            operator = ComparisonOperator.EQUALS  # Default fallback
        
        condition = QueryCondition(column=column, operator=operator, value=value)
        self.group_by.having_conditions.append(condition)
        return self
    
    def order_by(self, column: str, direction: Union[OrderDirection, str] = OrderDirection.ASC,
                table_alias: str = None) -> 'UniversalQueryBuilder':
        """Add ORDER BY clause"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                dir_str = direction.value if isinstance(direction, OrderDirection) else direction
                self.mongo_builder.order_by(column, dir_str)
            return self
        
        if isinstance(direction, str):
            direction = OrderDirection.ASC if direction.upper() == 'ASC' else OrderDirection.DESC
        
        order_obj = QueryOrderBy(column=column, direction=direction, table_alias=table_alias)
        self.order_by.append(order_obj)
        return self
    
    def limit(self, count: int) -> 'UniversalQueryBuilder':
        """Add LIMIT clause"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.limit(count)
            return self
        
        self.limit_count = count
        return self
    
    def offset(self, count: int) -> 'UniversalQueryBuilder':
        """Add OFFSET clause"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.skip(count)
            return self
        
        self.offset_count = count
        return self
    
    def paginate(self, page: int, per_page: int) -> 'UniversalQueryBuilder':
        """Add pagination (LIMIT + OFFSET)"""
        offset = (page - 1) * per_page
        return self.limit(per_page).offset(offset)
    
    # INSERT, UPDATE, DELETE methods
    
    def insert_into(self, table: str) -> 'UniversalQueryBuilder':
        """Start INSERT query"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.from_collection(table)
            return self
        
        self.query_type = QueryType.INSERT
        self.from_table = table
        return self
    
    def values(self, **column_values: Any) -> 'UniversalQueryBuilder':
        """Add INSERT values"""
        if self.database_type == DatabaseType.MONGODB:
            return self
        
        self.insert_columns = list(column_values.keys())
        self.insert_values = list(column_values.values())
        return self
    
    def update_table(self, table: str) -> 'UniversalQueryBuilder':
        """Start UPDATE query"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.from_collection(table)
            return self
        
        self.query_type = QueryType.UPDATE
        self.from_table = table
        return self
    
    def set_values(self, **column_values: Any) -> 'UniversalQueryBuilder':
        """Add UPDATE SET values"""
        if self.database_type == DatabaseType.MONGODB:
            return self
        
        self.update_assignments.update(column_values)
        return self
    
    def delete_from(self, table: str) -> 'UniversalQueryBuilder':
        """Start DELETE query"""
        if self.database_type == DatabaseType.MONGODB:
            if self.mongo_builder:
                self.mongo_builder.from_collection(table)
            return self
        
        self.query_type = QueryType.DELETE
        self.from_table = table
        return self
    
    # Build methods
    
    def build(self) -> Tuple[str, List[Any]]:
        """Build the final query"""
        if self.database_type == DatabaseType.MONGODB:
            return self._build_mongodb_query()
        else:
            return self._build_sql_query()
    
    def _build_sql_query(self) -> Tuple[str, List[Any]]:
        """Build SQL query"""
        if self.query_type == QueryType.SELECT:
            return self._build_select_query()
        elif self.query_type == QueryType.INSERT:
            return self._build_insert_query()
        elif self.query_type == QueryType.UPDATE:
            return self._build_update_query()
        elif self.query_type == QueryType.DELETE:
            return self._build_delete_query()
        else:
            raise ValueError(f"Unsupported query type: {self.query_type}")
    
    def _build_select_query(self) -> Tuple[str, List[Any]]:
        """Build SELECT query"""
        if not self.from_table:
            raise ValueError("FROM table is required for SELECT query")
        
        query_parts = []
        params = []
        
        # SELECT clause
        columns = ', '.join(self.select_columns) if self.select_columns else '*'
        query_parts.append(f"SELECT {columns}")
        
        # FROM clause
        table_ref = f"{self.from_table} AS {self.table_alias}" if self.table_alias else self.from_table
        query_parts.append(f"FROM {table_ref}")
        
        # JOIN clauses
        for join in self.joins:
            join_sql, join_params = join.to_sql(self.database_type)
            query_parts.append(join_sql)
            params.extend(join_params)
        
        # WHERE clause
        if self.where_conditions:
            where_parts = []
            for condition in self.where_conditions:
                cond_sql, cond_params = condition.to_sql(self.database_type)
                where_parts.append(cond_sql)
                params.extend(cond_params)
            query_parts.append(f"WHERE {' AND '.join(where_parts)}")
        
        # GROUP BY clause
        if self.group_by:
            group_sql, group_params = self.group_by.to_sql(self.database_type)
            if group_sql:
                query_parts.append(group_sql)
                params.extend(group_params)
        
        # ORDER BY clause
        if self.order_by:
            order_parts = [order.to_sql() for order in self.order_by]
            query_parts.append(f"ORDER BY {', '.join(order_parts)}")
        
        # LIMIT/OFFSET clause
        if self.limit_count:
            limit_clause = self.dialect.get_limit_clause(self.limit_count, self.offset_count)
            query_parts.append(limit_clause)
        
        return ' '.join(query_parts), params
    
    def _build_insert_query(self) -> Tuple[str, List[Any]]:
        """Build INSERT query"""
        if not self.from_table or not self.insert_columns:
            raise ValueError("Table and columns are required for INSERT query")
        
        columns_str = ', '.join(self.insert_columns)
        placeholders = ', '.join(['%s'] * len(self.insert_values))
        
        query = f"INSERT INTO {self.from_table} ({columns_str}) VALUES ({placeholders})"
        return query, self.insert_values
    
    def _build_update_query(self) -> Tuple[str, List[Any]]:
        """Build UPDATE query"""
        if not self.from_table or not self.update_assignments:
            raise ValueError("Table and SET values are required for UPDATE query")
        
        query_parts = []
        params = []
        
        # UPDATE table SET
        set_parts = []
        for column, value in self.update_assignments.items():
            set_parts.append(f"{column} = %s")
            params.append(value)
        
        query_parts.append(f"UPDATE {self.from_table} SET {', '.join(set_parts)}")
        
        # WHERE clause
        if self.where_conditions:
            where_parts = []
            for condition in self.where_conditions:
                cond_sql, cond_params = condition.to_sql(self.database_type)
                where_parts.append(cond_sql)
                params.extend(cond_params)
            query_parts.append(f"WHERE {' AND '.join(where_parts)}")
        
        return ' '.join(query_parts), params
    
    def _build_delete_query(self) -> Tuple[str, List[Any]]:
        """Build DELETE query"""
        if not self.from_table:
            raise ValueError("Table is required for DELETE query")
        
        query_parts = [f"DELETE FROM {self.from_table}"]
        params = []
        
        # WHERE clause
        if self.where_conditions:
            where_parts = []
            for condition in self.where_conditions:
                cond_sql, cond_params = condition.to_sql(self.database_type)
                where_parts.append(cond_sql)
                params.extend(cond_params)
            query_parts.append(f"WHERE {' AND '.join(where_parts)}")
        
        return ' '.join(query_parts), params
    
    def _build_mongodb_query(self) -> Tuple[str, List[Any]]:
        """Build MongoDB query"""
        if not self.mongo_builder:
            raise ValueError("MongoDB builder not initialized")
        
        if self.query_type == QueryType.SELECT:
            query = self.mongo_builder.build_find_query()
        else:
            raise ValueError(f"MongoDB query type {self.query_type} not implemented in builder")
        
        return json.dumps(query), []
    
    def to_sql(self) -> str:
        """Get SQL string (without parameters)"""
        query, params = self.build()
        
        if self.database_type == DatabaseType.MONGODB:
            return query  # Already JSON string
        
        # Simple parameter substitution for display purposes
        sql = query
        for param in params:
            if isinstance(param, str):
                sql = sql.replace('%s', f"'{param}'", 1)
            elif param is None:
                sql = sql.replace('%s', 'NULL', 1)
            else:
                sql = sql.replace('%s', str(param), 1)
        
        return sql
    
    def reset(self) -> 'UniversalQueryBuilder':
        """Reset query builder to initial state"""
        self.query_type = None
        self.select_columns = []
        self.from_table = None
        self.table_alias = None
        self.joins = []
        self.where_conditions = []
        self.group_by = None
        self.order_by = []
        self.limit_count = None
        self.offset_count = None
        self.insert_columns = []
        self.insert_values = []
        self.update_assignments = {}
        
        if self.mongo_builder:
            self.mongo_builder = MongoQueryBuilder()
        
        return self
    
    def clone(self) -> 'UniversalQueryBuilder':
        """Create a copy of the query builder"""
        new_builder = UniversalQueryBuilder(self.database_type)
        
        # Copy all attributes
        new_builder.query_type = self.query_type
        new_builder.select_columns = self.select_columns.copy()
        new_builder.from_table = self.from_table
        new_builder.table_alias = self.table_alias
        new_builder.joins = self.joins.copy()
        new_builder.where_conditions = self.where_conditions.copy()
        new_builder.group_by = self.group_by
        new_builder.order_by = self.order_by.copy()
        new_builder.limit_count = self.limit_count
        new_builder.offset_count = self.offset_count
        new_builder.insert_columns = self.insert_columns.copy()
        new_builder.insert_values = self.insert_values.copy()
        new_builder.update_assignments = self.update_assignments.copy()
        
        return new_builder


# Convenience functions
def query_builder(database_type: DatabaseType = DatabaseType.POSTGRESQL) -> UniversalQueryBuilder:
    """Create a new query builder instance"""
    return UniversalQueryBuilder(database_type)


def sql_builder() -> UniversalQueryBuilder:
    """Create SQL query builder (PostgreSQL by default)"""
    return UniversalQueryBuilder(DatabaseType.POSTGRESQL)


def mysql_builder() -> UniversalQueryBuilder:
    """Create MySQL query builder"""
    return UniversalQueryBuilder(DatabaseType.MYSQL)


def mongo_builder() -> UniversalQueryBuilder:
    """Create MongoDB query builder"""
    return UniversalQueryBuilder(DatabaseType.MONGODB)