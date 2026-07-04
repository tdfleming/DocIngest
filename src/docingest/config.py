from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # MinIO (S3-compatible blob storage)
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "docingest"

    # FastEmbed (local embeddings)
    fastembed_model: str = "BAAI/bge-small-en-v1.5"

    # Reranking (local cross-encoder, ONNX via FastEmbed)
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"

    # MongoDB
    mongodb_uri: str = "mongodb://mongodb:27017"
    mongodb_database: str = "docingest"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # Redis
    redis_url: str = "redis://redis:6379"

    # Processing
    chunk_max_tokens: int = 512
    chunk_overlap_percent: int = 10
    chunking_strategy: str = "fixed"
    embedding_batch_size: int = 100
    embedding_dimensions: int = 384

    # Rate Limiting
    default_rate_limit: int = 100

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    # Telemetry (opt-in, anonymous — OFF by default; see services/telemetry.py)
    telemetry_enabled: bool = False
    telemetry_endpoint: str = "https://telemetry.docingest.dev/v1/heartbeat"
    telemetry_interval_hours: int = 24

    # Graph RAG
    graph_rag_enabled: bool = False
    spacy_model: str = "en_core_web_lg"
    entity_confidence_threshold: float = 0.7
    max_entities_per_chunk: int = 50

    # Community detection
    community_resolutions: list[float] = [0.1, 0.5, 1.0]
    community_max_chunks: int = 50
    community_max_summary_sentences: int = 5


settings = Settings()
