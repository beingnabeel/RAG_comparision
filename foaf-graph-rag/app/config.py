from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    API_TITLE: str = "FoaF Graph RAG API"
    API_VERSION: str = "1.0.0"
    API_PORT: int = 8000

    # LLM Settings (Google Gemini)
    GOOGLE_API_KEY: str = ""
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TEMPERATURE: float = 0.0

    # Fuseki Settings
    FUSEKI_ENDPOINT: str = "http://localhost:3030/foaf"

    @property
    def FUSEKI_QUERY_ENDPOINT(self) -> str:
        return f"{self.FUSEKI_ENDPOINT}/query"

    @property
    def FUSEKI_UPDATE_ENDPOINT(self) -> str:
        return f"{self.FUSEKI_ENDPOINT}/update"

    @property
    def FUSEKI_DATA_ENDPOINT(self) -> str:
        return f"{self.FUSEKI_ENDPOINT}/data"

    # Graph Settings
    DEFAULT_NAMESPACE: str = "http://example.org/foaf-poc/"
    ONTOLOGY_GRAPH_URI: str = "http://example.org/foaf-poc/ontology"
    DATA_GRAPH_URI: str = "http://example.org/foaf-poc/data"

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
