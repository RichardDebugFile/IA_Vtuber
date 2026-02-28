"""
Database connection and session management for Casiopy Memory Service
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
from loguru import logger

# Cargar variables de entorno
load_dotenv()

# Configuración de base de datos
POSTGRES_USER = os.getenv("POSTGRES_USER", "memory_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "casiopy_memory_2024")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")
POSTGRES_DB = os.getenv("POSTGRES_DB", "casiopy_memory")

# URL de conexión PostgreSQL (asyncpg para async support)
DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Crear engine asíncrono
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True para debug SQL
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verificar conexiones antes de usar
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Base para modelos SQLAlchemy
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency para obtener sesión de base de datos en FastAPI

    Uso:
        @app.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """
    Inicializar conexión a base de datos y verificar que esté accesible
    """
    try:
        async with engine.begin() as conn:
            # Verificar que pgvector está instalado
            result = await conn.execute(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
            )
            vector_installed = (await result.fetchone())[0] > 0

            if not vector_installed:
                logger.warning("⚠️  Extensión pgvector no encontrada")
            else:
                logger.info("✅ Extensión pgvector detectada")

            # Verificar conexión
            result = await conn.execute("SELECT version()")
            pg_version = (await result.fetchone())[0]
            logger.info(f"✅ Conectado a PostgreSQL: {pg_version}")

        logger.info("✅ Base de datos inicializada correctamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error al conectar con la base de datos: {e}")
        return False


async def close_db():
    """
    Cerrar conexiones de base de datos
    """
    await engine.dispose()
    logger.info("🔌 Conexiones de base de datos cerradas")
