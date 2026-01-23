import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Type, Union

from common.config import MYSQL_CFG

from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
import anyio
from anyio import to_thread, Semaphore, get_cancelled_exc_class, CancelScope

logger = logging.getLogger("mysql")

class MySQL:
    _instance: Optional[MySQLConnectionPool] = None
    _semaphore = Semaphore(MYSQL_CFG.get("pool_size", 5))

    @classmethod
    def get_pool(cls) -> MySQLConnectionPool:
        if cls._instance is None:
            cls._instance = MySQLConnectionPool(**MYSQL_CFG)
        return cls._instance

    @classmethod
    @contextmanager
    def connection(cls):
        pool = cls.get_pool()
        con = None
        try:
            con = pool.get_connection()
            yield con
        except Error as e:
            logger.error(f"Database error: {e}")
            if con:
                con.rollback()
            raise
        finally:
            if con and con.is_connected():
                con.close()
    
    @classmethod
    def execute_query(
        cls,
        query,
        params = None,
        fetch_one = False
    ):
        with cls.connection() as con:
            cursor = None
            try:
                cursor = con.cursor(dictionary=True)
                cursor.execute(query, params or ())
                
                if fetch_one:
                    result = cursor.fetchone()
                    logger.debug(f"Query executed (fetch_one): {query[:100]}...")
                    return result
                else:
                    result = cursor.fetchall()
                    logger.debug(f"Query executed: {query[:100]}... | Rows returned: {len(result)}")
                    return result
            finally:
                if cursor:
                    cursor.close()
    
    @classmethod
    def execute_update(
        cls, 
        query, 
        params = None
    ):
        with cls.connection() as con:
            cursor = None
            try:
                cursor = con.cursor(buffered=True)
                cursor.execute(query, params or ())
                con.commit()
                affected_rows = cursor.rowcount
                logger.debug(f"Update executed: {query[:100]}... | Affected rows: {affected_rows}")
                return affected_rows
            finally:
                if cursor:
                    cursor.close()
    
    @classmethod
    def execute_insert(
        cls, 
        query, 
        params = None
    ):
        with cls.connection() as con:
            cursor = None
            try:
                cursor = con.cursor()
                cursor.execute(query, params or ())
                con.commit()
                last_id = cursor.lastrowid
                logger.debug(f"Insert executed: {query[:100]}... | Last ID: {last_id}")
                return last_id
            finally:
                if cursor:
                    cursor.close()
    
    @classmethod
    def execute_many(
        cls, 
        query, 
        params_list
    ):
        with cls.connection() as con:
            cursor = None
            try:
                cursor = con.cursor()
                cursor.executemany(query, params_list)
                con.commit()
                affected_rows = cursor.rowcount
                logger.debug(f"Bulk operation: {query[:100]}... | Affected rows: {affected_rows}")
                return affected_rows
            finally:
                if cursor:
                    cursor.close()
    
    @classmethod
    async def aexecute_query(cls, query, params=None, fetch_one=False):
        async with cls._semaphore:
            return await to_thread.run_sync(cls.execute_query, query, params, fetch_one)
    @classmethod
    async def aexecute_update(cls, query, params=None):
        async with cls._semaphore:
            return await to_thread.run_sync(cls.execute_update, query, params)
    @classmethod
    async def aexecute_insert(cls, query, params=None):
        async with cls._semaphore:
            return await to_thread.run_sync(cls.execute_insert, query, params)
    @classmethod
    async def aexecute_many(cls, query, params_list):
        async with cls._semaphore:
            return await to_thread.run_sync(cls.execute_many, query, params_list)