import os
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

log = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages asynchronous database connections and session lifecycle.
    """

    def __init__(self, database_url: str = None):
        """
        Initialize the database engine.
        Defaults to environment variable 'DATABASE_URL' if not provided.
        Example: mysql+aiomysql://user:pass@localhost/fundametrics_db
        """
        self.url = database_url or os.getenv("DATABASE_URL")
        if not self.url:
            log.error("DATABASE_URL not found in environment variables.")
            raise ValueError("DATABASE_URL is required.")

        self.engine = create_async_engine(
            self.url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        log.info(f"DatabaseManager initialized for {self.url.split('@')[-1]}")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provides an async session via a generator (useful for dependency injection).
        """
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def check_connection(self) -> bool:
        """
        Verifies the database connection.
        """
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            log.error(f"Database connection check failed: {e}")
            return False

    async def close(self):
        """
        Gracefully closes the engine.
        """
        await self.engine.dispose()
        log.info("Database engine disposed.")

# Global instance for shared use
db_manager = None

def init_db(url: str = None):
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager(url)
    return db_manager
