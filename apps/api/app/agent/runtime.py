from app.agent.executor import LangGraphAgentExecutor
from app.agent.nodes.evaluate import EvaluationDependencies
from app.core.config import Settings
from app.evaluation.deepgaze_client import DeepGazeClient
from app.evaluation.vision_evaluator import VisionEvaluator
from app.poster.renderer import PosterRenderer
from app.providers.embedding.ollama import create_ollama_embeddings
from app.providers.image.ark import ArkImageProvider
from app.providers.llm.deepseek import DeepSeekProvider
from app.providers.vision.ark import ArkVisionProvider
from app.rag.langchain_chroma_store import ChromaVectorStore, create_remote_chroma
from app.rag.repository import KnowledgeRepository
from app.rag.retriever import KnowledgeRetriever


def create_runtime_executor(settings: Settings) -> LangGraphAgentExecutor:
    embeddings = create_ollama_embeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
        timeout_seconds=settings.embedding_timeout_seconds,
    )
    chroma = create_remote_chroma(
        chroma_url=settings.chroma_url,
        collection_name=settings.rag_collection_name,
        embedding_function=embeddings,
    )
    retriever = KnowledgeRetriever(
        KnowledgeRepository(settings.data_dir / "knowledge"),
        ChromaVectorStore(chroma),
    )
    return LangGraphAgentExecutor(
        retriever=retriever,
        text_provider=DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_text_model,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.text_model_timeout_seconds,
        ),
        image_provider=ArkImageProvider(
            api_key=settings.ark_api_key,
            model=settings.ark_image_model,
            base_url=settings.ark_base_url,
            default_size=settings.ark_image_size,
            response_format=settings.ark_image_response_format,
            output_format=settings.ark_image_output_format,
            timeout_seconds=settings.image_model_timeout_seconds,
        ),
        renderer=PosterRenderer(),
        evaluation=EvaluationDependencies(
            deepgaze=DeepGazeClient(
                base_url=settings.deepgaze_base_url,
                timeout_seconds=settings.deepgaze_timeout_seconds,
            ),
            vision=VisionEvaluator(
                ArkVisionProvider(
                    api_key=settings.ark_api_key,
                    model=settings.ark_vision_model,
                    base_url=settings.ark_base_url,
                    timeout_seconds=settings.vision_model_timeout_seconds,
                )
            ),
        ),
        checkpoint_path=settings.langgraph_checkpoint_path,
    )
