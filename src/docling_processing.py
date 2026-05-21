import asyncio
from typing import Optional
from typing_extensions import Format
from docling_core.types.doc import DocItemLabel
from docling_core.types.doc import PictureItem
from docling_core.types.doc import PageItem,TextItem
from docling_core.types.doc import ImageRefMode
from docling.document_converter import PdfFormatOption
from config.log_config import LoggerConfig
from config.config_settings import ConfigSettings
import os
import io
import traceback
import pathlib
import threading
import psutil
import time
import ollama
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions, PictureDescriptionApiOptions,TableStructureOptions,TableFormerMode
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend, DoclingParseDocumentBackend
from docling.datamodel.base_models import InputFormat, BoundingBox
from PIL import ImageEnhance, ImageOps
import cv2
import json

class DoclingProcessing:
    def __init__(self,logger,settings,system_prompt,user_prompt):
        self.logger = logger.get_logger()
        self.settings = settings
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.converter = self.__init_converter()
        
    

    def __init_converter(self):
        pipeline_options = self.__init_pipeline_options()
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options, backend=DoclingParseDocumentBackend)
            }
        )
    
    def __init_pipeline_options(self):
        # Prepare custom params for VLM
        custom_params = {
            "model": self.settings.docling_config.vision_model_name,
            "system": f"{self.system_prompt}\n\n{self.user_prompt}",
            "temperature": 0.1,
            "top_p": 0.9,
        }
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options = AcceleratorOptions(num_threads=1, device='cpu')
        pipeline_options.do_table_structure = self.settings.docling_config.do_table_structure
        pipeline_options.do_picture_description = self.settings.docling_config.do_picture_description
        pipeline_options.generate_picture_images = self.settings.docling_config.generate_picture_images
        pipeline_options.do_ocr = self.settings.docling_config.do_ocr
        pipeline_options.table_structure_options=TableStructureOptions(mode=TableFormerMode.ACCURATE)
        pipeline_options.enable_remote_services=self.settings.docling_config.enable_remote_services
        pipeline_options.generate_page_images = self.settings.docling_config.generate_page_images
        pipeline_options.images_scale = self.settings.docling_config.images_scale
        pipeline_options.table_structure_options.do_cell_matching = self.settings.docling_config.do_cell_matching
        return pipeline_options


    async def document_processing_extract(self,file_name_dir:str,chunk_pdf_file_path: str,chunk_pdf_file_name:str):
        picture_desc_result = []
        pdf_chunk_result = {}
        img_counter = 0
        try:
            start_time = time.time()
            # result = self.converter.convert(chunk_pdf_file_path) # Blocking
            result = await asyncio.to_thread(self.converter.convert, chunk_pdf_file_path)
            pdf_document = result.document
            chunk_pdf_markdown_filepath = os.path.join(self.settings.datasource_config.markdown_files_path,file_name_dir,chunk_pdf_file_name,f"{chunk_pdf_file_name}.md")
            os.makedirs(os.path.dirname(chunk_pdf_markdown_filepath), exist_ok=True)
            pdf_document.save_as_markdown(chunk_pdf_markdown_filepath,image_mode=ImageRefMode.REFERENCED,page_break_placeholder="<!-- Page Break -->")
            
            for element, _level in pdf_document.iterate_items():
                if isinstance(element, PictureItem):
                    element.annotations
                    # image_file_name = element.image.uri if element.image else None
                    self.logger.info(f"Image file name: {element.meta}")
                    if element.image is None:
                        self.logger.warning(f"No image data for image_{img_counter:06d}, skipping.")
                        img_counter += 1
                        continue
                    img_byt_arr = io.BytesIO()
                    raw_image = element.image.pil_image
                    enhanced_image = self.__enhance_image_for_ocr(raw_image,f"image_{img_counter:06d}",chunk_pdf_file_name)
                    if enhanced_image is None:
                        self.logger.warning(f"Enhancement failed for image_{img_counter:06d}, skipping.")
                        img_counter += 1
                        continue
                    
                    self.logger.info(f"Enhanced image image_{img_counter:06d} dimensions: {enhanced_image.size}")
                    enhanced_image.save(img_byt_arr, format="PNG")
                    img_byt_arr.seek(0)
                    img_bytes = img_byt_arr.getvalue()
                    response = await self.picture_description_extraction(img_bytes,chunk_pdf_file_name,img_counter)
                    if response is not None:
                        picture_description = response.message.content
                        self.logger.info(f"\n Raw Picture description response: {picture_description} \n")
                        
                        if not picture_description:
                            self.logger.warning(f"Empty response content for image_{img_counter:06d}, skipping.")
                            picture_desc_result.append({f"image_{img_counter:06d}": 'FAILURE'})
                            img_counter += 1
                            continue
                        
                        # Robust JSON extraction and validation
                        start_idx = picture_description.find('{') if picture_description.find('{') != -1 else 0
                        end_idx = picture_description.rfind('}') if picture_description.rfind('}') != -1 else 0
                        
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            clean_json_str = picture_description[start_idx:end_idx+1].strip()
                            try:
                                # Validate JSON content
                                json_data = json.loads(clean_json_str)
                                
                                # Save as formatted JSON
                                picture_desc_json_filename = os.path.join(self.settings.datasource_config.markdown_files_path,file_name_dir,chunk_pdf_file_name,f"image_{img_counter:06d}.json")
                                with open(picture_desc_json_filename,"w") as f:
                                    json.dump(json_data, f, indent=4)
                                
                                picture_desc_result.append({f"image_{img_counter:06d}":'SUCCESS'})
                                self.logger.info(f"Successfully saved validated JSON for image_{img_counter:06d}")
                            except json.JSONDecodeError as e:
                                self.logger.error(f"JSON validation failed for image_{img_counter:06d}: {e}")
                                self.logger.error(f"Attempted to parse: {clean_json_str}")
                                picture_desc_result.append({f"image_{img_counter:06d}":'FAILURE'})
                        else:
                            self.logger.warning(f"No valid JSON object delimiters found in response for image_{img_counter:06d}")
                            picture_desc_result.append({f"image_{img_counter:06d}":'FAILURE'})
                    else:
                        self.logger.warning("Skipping picture description due to vision model failure.")
                        picture_desc_result.append({f"image_{img_counter:06d}":'FAILURE'})
                    img_counter += 1
            self.logger.info(f"Duration:{time.time()-start_time}")
            pdf_chunk_result[chunk_pdf_file_name] = picture_desc_result
            return pdf_chunk_result   
        except Exception as e:  
            self.logger.error(f"Error in processing document {chunk_pdf_file_name} present at the file path {chunk_pdf_file_path}: {e}", exc_info=True)
            picture_desc_result.append({f"image_{img_counter:06d}":'FAILURE'})
            pdf_chunk_result[chunk_pdf_file_name] = picture_desc_result
            return pdf_chunk_result


    async def picture_description_extraction(self,img_bytes,chunk_pdf_file_name,img_counter):
        try:
            self.logger.info(f"\n Parsing Image image_{img_counter:06d} (size: {len(img_bytes)} bytes) from PDF file {chunk_pdf_file_name} \n")
            start_time = time.time()
            # Using asyncio.to_thread for blocking ollama call if AsyncClient is not used
            response = await asyncio.to_thread(
                ollama.chat,
                model=self.settings.docling_config.vision_model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.user_prompt, "images": [img_bytes]}
                ],
                think=False,
                options={
                    "temperature": 0.1,
                    "repeat_penalty": 1.1,       # ← Keep (prevents repetition)
                    "num_predict": 30000         # ← Added (max tokens)
                    #,"stop": ["```", "Drafting", "Final JSON", "Constructing", "Here is the", "JSON:", "\n\n"]   # ← Prevent markdown blocks
                }
                ,format="json"
            )
            self.logger.info(f"Duration for picture image_{img_counter:06d} description extraction:{time.time()-start_time}")
            self.logger.info(f"Response:{response}")
            return response
        except Exception as e:
            self.logger.error(f"Error processing images from document {chunk_pdf_file_name}: {e}")
            return None


    def __enhance_image_for_ocr(self,pil_img,image_name,chunk_pdf_file_name):
        try:
            self.logger.info(f"Enhancing image {image_name} from document {chunk_pdf_file_name}")
            # Keep in RGB mode as vision models generally prefer it over L (grayscale)
            img = pil_img.convert("L")
            img = ImageEnhance.Contrast(img).enhance(2.0)
            img = ImageEnhance.Sharpness(img).enhance(2.0)
            self.logger.info(f"Image {image_name} from document {chunk_pdf_file_name} enhanced successfully (L)")
            return img
        except Exception as e:
            self.logger.error(f"Error enhancing image {image_name} from document {chunk_pdf_file_name}: {e}")
            return None


