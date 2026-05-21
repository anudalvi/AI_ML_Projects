#from src.assembly_instruction_data_process import AssemblyInstructionDataExtractor
from anyio import sleep
from config.config_settings import ConfigSettings
import logging
import os
import traceback
from config.log_config import LoggerConfig
from src.docling_processing import DoclingProcessing
from src.Fetch_IKEA_Product_Details import FetchIKEAProductDetails
import pandas as pd
import asyncio
from bs4 import BeautifulSoup
import re
import pandas as pd
from src.vl_model_client_config import vl_model_client_input
from src.knowledge_base_vectorstore_processing import KnowledgeBaseVectorstoreProcessing
from src.data_extraction_processing import DataExtractionProcessing

async def main():
    doc_settings = ConfigSettings()
    logger_config = LoggerConfig()
    logger = logger_config.get_logger()
    try:
        '''ikea_products = FetchIKEAProductDetails(logger,doc_settings)
        vl_model_input = vl_model_client_input(logger,doc_settings)
        data_extraction_processing = DataExtractionProcessing(logger=logger,settings=doc_settings)
        vector_data_extractor = KnowledgeBaseVectorstoreProcessing(logger,doc_settings)'''
        ikea_products = FetchIKEAProductDetails()
        vl_model_input = vl_model_client_input()
        data_extraction_processing = DataExtractionProcessing()
        vector_data_extractor = KnowledgeBaseVectorstoreProcessing()
        header = {
            "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language":"en-US,en;q=0.9",
            "Sec-Fetch-Dest":"document",
            "Sec-Fetch-Mode":"navigate",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:148.0) Gecko/20100101 Firefox/148.0",
            "Cookie":"guest=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImVxSFFLR3duR3hfV3dJZkx0RGpaeDA5MTUzS2xSam5fVE1nVUlMYlJ5RncifQ.eyJpc3MiOiJodHRwczovL2FwaS5pbmdrYS5pa2VhLmNvbS9ndWVzdCIsInN1YiI6IjZhODgzMDJlLTc1NjQtNDcxNi05YzNjLWE2YTNmYzlkNTFiYyIsInJldGFpbFVuaXQiOiJubCIsImlhdCI6MTc3MjQwNjgyMiwiZXhwIjoxNzc0OTk4ODIyfQ.PRoyk_UF_XH5QAdJl07t7eL5uuQPfoauDs2tZd2LHlqqcNVGJGRGVdIpbXZ_Y0H-raS1_KG70KksGwg0fL5yKazhnW5OhLW2niOjj-mkFY-bPWEyCHV9e2a-4_9rOLkoJG-cLT2HGGIv5f0bVEUc6KpC-HMJZgHZ2DGFBuYJID0; ikea_geo=NL; _cs_mk_ga=0.4831464114045395_1772408086967; FPGSID=1.1772408087.1772408087.G-S4EX53B760.uP0KiX7UO841fYn2ajMqWA; _rdt_uuid=1771803493114.a508122e-9754-4932-9c37-a8390a988dbf; tfpsi=5ec8ed3a-d445-40d8-967f-daa195df57ed; _uetsid=3d097da015c711f19aa3fd4b495c318f; _uetvid=8e27d6c0104711f186952d9d53d01d19"
        }
        await sleep(10)
        response = ikea_products.fetch_product_details(url_path = "cat/products-products/",headers=header)
        #print(response)
        if response is None:
            logger.error("Failed to fetch product details")
            return
        product_links = ikea_products.parse_product_category_links(response)
        if product_links is None:
            logger.error("Failed to parse product links")
            return
        df_product_links =ikea_products.parse_product_links(product_links,header)
        if df_product_links is None:
            logger.error("Failed to parse product links")
            return
        product_download_pdf_results = await ikea_products.parse_product_details_and_manual_download(df_product_links,header)
        if product_download_pdf_results is None:
            logger.error("Failed to parse product details and manual download")
            return
        for input in product_download_pdf_results:
            #pdf_markdown_output = await vl_model_input.generate_markdown_output(result)
            #logger.info(f"PDF Markdown Output: {pdf_markdown_output}")
            node_source_data = await data_extraction_processing.run_extraction_pipeline(input)
            await vector_data_extractor.generate_graph_nodes_relationships(node_source_data,input)
            #await vector_data_extractor.vector_graph_store_process(result)
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)  
    
    
asyncio.run(main())


