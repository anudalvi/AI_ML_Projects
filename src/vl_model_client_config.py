#import docling_processing
from pathlib import Path
import pymupdf
import requests
from config.config_settings import ConfigSettings
from config.log_config import LoggerConfig
import re
import pandas as pd
import asyncio
import threading
import os
#from src.docling_process_test2 import DoclingProc1
from src.docling_processing import DoclingProcessing
import json


class vl_model_client_input:
    '''def __init__(self,logger=None,settings=None):
        self.logger = logger if logger is not None else LoggerConfig().get_logger()
        self.settings = settings if settings is not None else ConfigSettings()'''
    
    def __init__(self):
        self.settings = ConfigSettings()
        self.logger = LoggerConfig().get_logger()

    def generate_system_prompt(self,result):
        system_prompt = ""
        try:
            product_details = ""
            product_material = ""
            safety_compliance = ""
            product_name_arr = ["", "", ""]
            product_category = ""

            #product_name_arr = result['PDF File Details']["product_name"].split(",")
            for row in result.get('Product Details', []):
                if row['header'] == 'Product details':
                    product_details = row['text'][:row['text'].index("Designer")].strip()
                    #product_details = product_details[:product_details.index("Designer")].strip()
                    #print(product_details)
                if row['header'] == 'Material':
                    product_material = row['text']
                    #print(product_material)
                if row['header'] == 'Safety and compliance':
                    safety_compliance = row['text']
                    #print(safety_compliance)
            
            for r in result.get('PDF File Details', []):
                if r['pdf_type'] == 'Assembly instructions':
                    product_name_arr = r['product_name'].split(',')
                    # Ensure at least 3 elements in product_name_arr
                    while len(product_name_arr) < 3:
                        product_name_arr.append("")
                    #print(product_name_arr)
                    product_category = r['product_category']
                    #print(product_category)

            replacements = {
                "product_name": product_name_arr[0] if len(product_name_arr) > 0 else "",
                #"product_dimension": product_name_arr[2] if len(product_name_arr) > 2 else "",
                #"product_color": product_name_arr[1] if len(product_name_arr) > 1 else "",
                "product_category": product_category,
                "product_details": product_details,
                "safety_compliance": safety_compliance
                #,"material": product_material
            }
            #print(f"Replacement: {replacements}")

            with open(self.settings.datasource_config.system_prompt_filepath, 'r') as f:
                for line in f:
                    # Safely replace placeholders to avoid KeyError with literal braces in the template (e.g. JSON examples)
                    formatted_line = line
                    for key, value in replacements.items():
                        placeholder = "{" + key + "}"
                        formatted_line = formatted_line.replace(placeholder, str(value))
                    system_prompt = system_prompt + formatted_line
            #print(f"System Prompt: {system_prompt}")
            return system_prompt
        except Exception as e:
            self.logger.error(f"Error generating system prompt: {e}", exc_info=True)
            return None
    
    
    def generate_user_prompt(self,result):
        try:
            with open(self.settings.datasource_config.user_prompt_filepath, 'r') as f:
                user_prompt = f.read()
            #print(f"User Prompt: {user_prompt}")
            return user_prompt
        except Exception as e:
            self.logger.error(f"Error generating user prompt: {e}", exc_info=True)
            return None
    
    async def generate_markdown_output(self,result):
        chunk_markdown_conversion_result = []
        pdf_markdown_result = []
        split_pdf_filepath = []
        system_prompt = ''
        user_prompt = ''
        if result is None:
            self.logger.error("Cannot generate markdown output: result is None")
            return None
        try:
            if result.get('PDF File Details') is None:
                self.logger.error("Cannot generate markdown output: result.get('PDF File Details') is None")
                return None
            pdf_file_path = None
            for r in result.get('PDF File Details', []):
                if r['pdf_type'].find('Assembly')!=-1:
                    pdf_file_path = r['pdf_file_path']
                    break
            if pdf_file_path is None:
                self.logger.error("Cannot generate markdown output: pdf_file_path is None")
                return None
            pdf_file_name = os.path.basename(pdf_file_path)
            system_prompt = self.generate_system_prompt(result)
            user_prompt = self.generate_user_prompt(result)
            
            with pymupdf.open(pdf_file_path) as doc:
                for i in range(0,doc.page_count,self.settings.datasource_config.page_split_length):
                    end_page = min(i+self.settings.datasource_config.page_split_length,doc.page_count)
                    file_name_dir = pdf_file_name.replace('.pdf','')
                    chunk_pdf_filepath = os.path.join(self.settings.datasource_config.pdf_file_split_folder,file_name_dir,f"{file_name_dir}_{i+1}_{end_page}.pdf")
                    chunk_file_name = f"{file_name_dir}_{i+1}_{end_page}.pdf"
                    os.makedirs(os.path.dirname(chunk_pdf_filepath), exist_ok=True)
                    with pymupdf.open() as chunk_doc:
                        chunk_doc.insert_pdf(doc,from_page=i,to_page=end_page-1)
                        chunk_doc.save(chunk_pdf_filepath)   
                    if os.path.getsize(chunk_pdf_filepath)>0:
                        self.logger.info(f"Docling processing initiated for PDF File Name: {chunk_pdf_filepath}")
                        docling_processing = DoclingProcessing(logger=self.logger,settings=self.settings,system_prompt=system_prompt,user_prompt=user_prompt)
                        chunk_markdown_output = await docling_processing.document_processing_extract(file_name_dir,chunk_pdf_filepath,chunk_file_name.replace('.pdf',''))
                        self.logger.info(f"Docling processing completed for PDF File Name {chunk_pdf_filepath}")
                        self.logger.info(f"Docling processing markdown conversion result for chunk file: {chunk_markdown_output}")
                        chunk_markdown_conversion_result.append(chunk_markdown_output)
                        #docling_processing = DoclingProc1(logger=self.logger,settings=self.settings,system_prompt=system_prompt,user_prompt=user_prompt)
                        #await docling_processing.document_processing_extract(chunk_pdf_filepath,chunk_file_name.replace('.pdf','')
            pdf_markdown_result.append({
                "pdf_file_path": pdf_file_path,
                "pdf_markdown_result": chunk_markdown_conversion_result
            })
            return pdf_markdown_result
        except Exception as e:
            self.logger.error(f"Error generating markdown output: {e}", exc_info=True)
            return pdf_markdown_result


    