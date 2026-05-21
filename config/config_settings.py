
from typing import Optional, Any, List, Dict, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
import requests
import os
# Dynamically find the project root (where this file is located)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

class LanceDBConfig(BaseModel):
    uri: Path = Field(default=(PROJECT_ROOT / Path('./data/LanceDB_data/IKEA_Catalog')).resolve(),description= 'location of lancedb OSS')
    tablename: str = Field(default = 'ikea_catalog', description = 'table name for documents')
    #embedding_dim: int = Field(default = 1024, ge=1, description = 'embedding dimension')
    similarity_metric: Literal["L2","cosine","dot"] = Field(default= 'cosine',description='Distance metric for similarity metric')
    nprobes: int = Field(default= 20, ge=1, description= "Number of probes for IVF index")
    index_type: Literal["IVF_PQ","IVF_HNSW_SQ"] = Field(default='IVF_PQ', description = 'Vector index type to be used')
    num_partitions: int = Field(default=16, description = 'Number of partiition in IVF index')
    num_sub_vectors: int = Field(default=4, description='Number of sub vectors to be created during Product Quantization (PQ)')
    create_table_mode: Literal['overwrite','append'] = Field(default='overwrite', description='create lancedb table mode')
    scalar_index_type: Literal['BTREE','BITMAP','LABEL_LIST'] = Field(default='BTREE', description = 'Scalar index type for scalar attributes (eg. numbers, categories)')
    embedding_model: str = Field(default = 'ibm-granite/granite-embedding-97m-multilingual-r2', description= 'Embedding model for LanceDB')
    embedding_model_save_path: Path = Field(default=(PROJECT_ROOT/Path('./embedding_model')).resolve(), description='Path to save the embedding models')



class FalkorDBConfig(BaseModel):
    falkor_host: str = Field(default='localhost', description='FalkorDB host')
    falkor_port: int = Field(default=6379, description='FalkorDB port') # 6379
    falkor_username: str = Field(default='admin', description='FalkorDB username')
    falkor_password: str = Field(default='admin', description='FalkorDB password')
    falkor_graph_name: str = Field(default='IKEACatalogDB', description='FalkorDB graph name')
    falkor_ddl_json_files: Path = Field(default=(PROJECT_ROOT/Path('./data/graph_vector_metadata/nodes_ddl')).resolve(), description='FalkorDB DDL JSON files path')


class ChunkSettingConfig(BaseModel):
    chunk_size: int = Field(default=512, description='Document chunk character size')
    chunk_overlap: int = Field(default=100, description = 'Document chunk overlap character size')
    language: Literal['markdown','python','java'] = Field(default='markdown', description='Language used to convert the document')
    page_chunk_split_length: int = Field(default= 5, description= "The no of pages at which the files needs to be splits.")
    process_max_workers: int = Field(default= 2, description= "Maximum number of files to be processed concurrently")

class MarkdownFileChunkingStrategyConfig(BaseModel):
    page_sections_pattern: str = Field(default= r'<!-- Page Break -->', description= 'Pattern to split the page sections')
    header_split_pattern: str = Field(default= r'\n\n(?=[^\n]+\n\n##)', description= 'Pattern to split the headers')
    #header_split_pattern: str = Field(default= r'\n\n(?=## )(?!## .{1,15}!\n)', description= 'Pattern to split the headers.Splits at double newlines before a header, UNLESS that header is a warning/all-caps title.')
    sub_header_split_pattern: str = Field(default= r'\n\n(?=[^\n]+\n\n###)', description= 'Pattern to split the sub headers')
    image_ref_pattern: str = Field(default= r'(!\[Image\].*?\))', description= 'Pattern to split the image references')    

class EmbeddingColumnsStrategyConfig(BaseModel):
    assembly_chunk_embedding_columns: Optional[Literal['step_name','action_text','parts','tools']] = Field(default = None, description = 'Columns to be used for embedding columns.')
    guidance_chunk_embedding_columns: Optional[Literal['step_name','action_text','safety_guidance','parts','tools']] = Field(default = None, description = 'Columns to be used for embedding columns.')


class DatasourceConfig(BaseModel):
    pfdfile_path: Path= Field(default= (PROJECT_ROOT/Path('./data/pdf_files')).resolve(), description= 'PDF source files fodler path')
    included_pattern: Literal["*.pdf", "*.md"] = Field(default='*.pdf', description='File extension types that can be parsed')
    excluded_pattern: Literal["**/node_modules/**", ".*"] = Field(default='**/node_modules/**', description='File/folders pattern to be excluded')
    binary_bool: bool=Field(default=True, description='Always true for docling PDF processing')
    refresh_interval: int = Field(default=10, description='How often to check for new incoming files')
    markdown_files_path: Path = Field(default= (PROJECT_ROOT/Path('./data/markdown_files')).resolve(), description='Folder to store the markdown files.')
    extracted_imagefile_path: Path = Field(default=(PROJECT_ROOT/Path('./data/images_extracted')).resolve(), description = 'Folder to store the images extracted from markdown file.')
    extracted_table_path: Path = Field(default=(PROJECT_ROOT/Path('./data/table_extracted_files')).resolve(), description = 'Folder to store the images extracted from markdown file.')
    img_extn: str = Field(default='png', description ='Image fiel format to save the extracted images from markdown file.')
    page_split_length: int = Field(default= 5, description= "The no of pages at which the files needs to be splits.")
    pdf_file_split_folder: Path = Field(default=(PROJECT_ROOT/Path("./data/pdf_files/splited_pdf_files").resolve()), description = "File path to save the PDF split files.")
    large_pdf_files_splitted: Path = Field(default=(PROJECT_ROOT/Path("./data/large_pdf_files").resolve()), description = "Folder where the large PDF files are moved after splitting.")
    user_manual_path: Path = Field(default=(PROJECT_ROOT/Path("./data/user_manuals").resolve()), description = "Folder where the user manuals are stored.")
    max_concurrent_files: int = Field(default= 4, description = 'Maximum number of files to be processed concurrently')
    system_prompt_filepath: Path = Field(default=(PROJECT_ROOT/Path("./data/prompts/system_prompt_template.txt").resolve()), description = "File path to store the system prompt.")
    user_prompt_filepath: Path = Field(default=(PROJECT_ROOT/Path("./data/prompts/user_prompt_template.txt").resolve()), description = "File path to store the user prompt.")
    nodes_mapping_filepath: Path = Field(default=(PROJECT_ROOT/Path("./data/graph_vector_metadata/nodes_mapping.json").resolve()), description = "File path to store the column mapping.")
    parent_data_folder:Path = Field(default=(PROJECT_ROOT/Path("./data").resolve()), description = "Folder where the parent data is stored.")
    table_source_column_mapping_filepath: Path = Field(default=(PROJECT_ROOT/Path("./data/lanceDB_metadata/table_source_column_mapping.json").resolve()), description = "File path to store the source column mapping.")
    table_definition_lancedb_filepath: Path = Field(default=(PROJECT_ROOT/Path("./data/lanceDB_metadata/table_definition_lancedb.json").resolve()), description = "File path to store the source column mapping.")



class DoclingConfig(BaseModel):
    enable_remote_services: bool = Field(default=True, description = 'Enable remote services')
    do_table_structure: bool = Field(default=True, description = 'Turn PDF boxes back into structural data')
    table_structure_options_mode: str = Field(default='accurate', description='Set to "fast" for speed or "accurate" for high precision')
    do_cell_matching: bool = Field(default=True, description = 'Enable cell matching')
    do_ocr: bool=Field(default=True, description='Support scanned PDF files')
    generate_page_images: bool = Field(default=False, description = 'To extract embedded images as PIL objects.')
    do_picture_description: bool = Field(default= False, description= 'Provide description of images using visual models')
    generate_picture_images: bool = Field(default= True, description = 'Extract images as image files')
    images_scale: float = Field(default=2.0, description='Higher values improve OCR accuracy for small European text.')
    document_timeout: int = Field(default=600, description='Maximum seconds to spend on a single large document.')
    picture_description_repo_id: str = Field(default='ibm-granite/granite-vision-3.3-2b', description='Repository ID for picture description model')
    picture_description_prompt: str = Field(default="""Provide a comprehensive, detailed description of this image. Include:
                                                    1. Main subject and overall composition
                                                    2. All visible text, labels, or captions
                                                    3. Charts, diagrams, or visual data elements
                                                    4. Colors, styles, and visual patterns
                                                    5. Relationships between elements
                                                    Format your response in clear, structured Markdown.""")
    header_threshold: float = Field(default=0.15, description='Header threshold')
    footer_threshold: float = Field(default=0.85, description='Footer threshold')
    vision_model_name: str = Field(default='qwen3.5:2b', description='Vision model used for picture description.')
    ocr_language: str = Field(default='en', description='Language for OCR processing')
    ocr_confidence: float = Field(default=0.80, description='Confidence threshold for OCR processing')
    
    #vision_model_name: str = Field(default='granite3.2-vision:latest', description='Vision model used for picture description.')
    
class IKEAConfig(BaseModel):
    language: str = Field(default='en', description='Language of the IKEA website')
    country: str = Field(default='nl', description='Country of the IKEA website')
    web_scrapping_config_file_path: Path = Field(default=(PROJECT_ROOT/Path("./data/Web_Scrapping_locator.json").resolve()), description = "File path to store the web scrapping config.")
    #ollama_url: str = Field(default='http://localhost:11434/v1/chat/completions', description='URL for the Ollama server')
    ollama_url: str = Field(default='http://localhost:11434', description='URL for the Ollama server')
    base_url: str = Field(default=f'https://www.ikea.com/{country}/{language}', description='Base URL for IKEA product details')
    @model_validator(mode='after')
    def _set_base_url(self):
        if self.language is None or self.country is None:
            raise ValueError('Language and country are required')
        self.base_url = f'https://www.ikea.com/{self.country}/{self.language}'
        return self

    


class ConfigSettings(BaseSettings):
    #Project Metadata Configurations
    project_name: str = Field(default='User Manual RAG Pipeline', description='RAG project name')
    environment: Literal['DEV', 'PROD', 'TEST'] = Field(default='DEV', description='Environment')
    version: str = Field(default='1.0.0', description='Version control of the project files')
    embedding_chunk_text_config: EmbeddingColumnsStrategyConfig = Field(default_factory=EmbeddingColumnsStrategyConfig)
    # Components Configurations
    lancedb: LanceDBConfig = Field(default_factory=LanceDBConfig)
    chunkconfig: ChunkSettingConfig = Field(default_factory=ChunkSettingConfig)
    markdown_chunk_config: MarkdownFileChunkingStrategyConfig = Field(default_factory=MarkdownFileChunkingStrategyConfig)
    datasource_config: DatasourceConfig = Field(default_factory=DatasourceConfig)
    docling_config: DoclingConfig = Field(default_factory=DoclingConfig)
    ikea_config: IKEAConfig = Field(default_factory=IKEAConfig)
    falkordb_config: FalkorDBConfig = Field(default_factory=FalkorDBConfig)

    # Logging and monitoring
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO", description="Log level")
    enable_tracing: bool = Field(default=False, description="Enable request tracing")
    log_name: str = Field(default="IKEA_Assembly_Instruction_Processing", description="Log file name")
    log_file_extn: str = Field(default=".log", description="Log file extension")
    log_file_path: Path = Field(default=(PROJECT_ROOT / Path('./logs')).resolve(), description='Log file path')
    log_file_name: str = Field(default="", description="Log file name")

    @model_validator(mode="after")
    def set_log_file_name(self) -> "ConfigSettings":
        """Sets the log file name dynamically if not already provided."""
        if not self.log_file_name:
            self.log_file_name = f"{self.environment}_{self.log_name}{self.log_file_extn}"
        return self


