import requests
from config.config_settings import ConfigSettings
from config.log_config import LoggerConfig
from bs4 import BeautifulSoup
import re
import pandas as pd
from playwright.async_api import async_playwright
import asyncio
import threading
import os

class FetchIKEAProductDetails:
    '''def __init__(self,logger=None,settings=None):
        self.logger = logger if logger is not None else LoggerConfig().get_logger()
        self.settings = settings if settings is not None else ConfigSettings()
        self.base_url = self.settings.ikea_config.base_url'''
    def __init__(self):
        self.settings = ConfigSettings()
        self.base_url = self.settings.ikea_config.base_url
        self.logger = LoggerConfig().get_logger()
    
    def fetch_product_details(self,url_path: str,headers:dict):
        try:
            response = requests.get(f"{self.base_url}/{url_path}", headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self.logger.error(f"Error fetching product details: {e}", exc_info=True)
            return None

    def parse_product_category_links(self,html_content: str):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            product_links = soup.find_all('a',href = re.compile("https://www.ikea.com/nl/en/cat/"))
            product_links_output = {link.text:link['href'] for link in product_links}
            #self.logger.info(f"Product Category Links: {product_links_output}")
            return product_links_output
        except Exception as e:
            self.logger.error(f"Error parsing product details: {e}", exc_info=True)
            return None

    def parse_product_links(self,product_links_data: dict,headers:dict):
        try:
            product_links_details = []
            product_data = []
            for title, link in product_links_data.items():
                try:
                    # Assuming product_links is title: link
                    product_data.append({"title": title, "link": link})
                except ValueError as e:
                    self.logger.warning(f"Skipping product '{title}' due to ValueError: {e}")
                    continue

            df_products = pd.DataFrame(product_data)
            #self.logger.info(f"Product Data: {df_products.to_string()}")
            self.logger.info(f"Total products: {len(df_products)}")
            #df_products.to_csv("/home/anu/RAG_AI_ML_Projects/IKEA_Assembly_Instruction_Processing/data/product_links.csv", index=False)
            #df = df_products[df_products['title'].str.contains("Beds") | df_products['title'].str.contains("Bookcases")]
            #self.logger.info(f"Total products after filtering: {len(df)}")
            
            for _, row in df_products.iterrows():
                response = self.fetch_product_details(url_path = row['link'].replace(self.base_url+'/',''),headers=headers)
                if response is None:
                    continue
                soup = BeautifulSoup(response, 'html.parser')
                product_links = soup.find_all('div',class_ = "plp-mastercard plp-fragment-wrapper plp-fragment-wrapper--grid")
                #print(product_links[0:2])
                #self.logger.info(f"Products Links Details: {product_links}")
                for p in product_links:
                    anchor = p.find('a')
                    if anchor is None or anchor.get('href') is None:
                        self.logger.warning(f"No product link found for product: {row['title']}")
                        continue
                    product_links_details.append({"title": row['title'], "parent_link": row['link'], "link": anchor['href']})

            #self.logger.info(f"Product Links Details: {product_links_details}")
            df_product_links = pd.DataFrame(product_links_details)
            #self.logger.info(f"Product Links Details: {df_product_links.to_string()}")
            df_product_links.to_csv("/home/anu/RAG_AI_ML_Projects/IKEA_Assembly_Instruction_Processing/data/product_links.csv", index=False)
            return df_product_links
        except Exception as e:
            self.logger.error(f"Error parsing product links: {e}", exc_info=True)
            return None
    
    async def parse_product_details_and_manual_download(self,df_product_links: pd.DataFrame,headers:dict):
        try:
            #df_product_links = df_product_links[df_product_links['link'].isin(['https://www.ikea.com/nl/en/p/lack-wall-shelf-unit-black-blue-00592870/','https://www.ikea.com/nl/en/p/kallax-shelving-unit-white-80275887/','https://www.ikea.com/nl/en/p/hemnes-glass-door-cabinet-with-3-drawers-grey-green-light-brown-stained-00596161/'])
            df_product_links = df_product_links[df_product_links['link'].isin(['https://www.ikea.com/nl/en/p/lack-wall-shelf-unit-black-blue-00592870/'])
            & df_product_links['title'].isin(['Bookcases & shelving units'])]
            self.logger.info(f"Total Records: {len(df_product_links)}")
            file_semaphore = asyncio.Semaphore(self.settings.datasource_config.max_concurrent_files)
            tasks = []
            for _,row in df_product_links.iterrows():
                task=asyncio.create_task(self.parse_product_links_playwright(row,headers,file_semaphore))
                tasks.append(task)
            results = await asyncio.gather(*tasks)
            self.logger.info(f"Results: {results}")
            return results
        except Exception as e:
            self.logger.error(f"Error parsing product details and manual download: {df_product_links['link'].values} \n Error: {e}", exc_info=True)
            return None
    
    async def parse_product_links_playwright(self,product_links_data_row:pd.Series,headers:dict,semaphore: asyncio.Semaphore):
        title_text_result = []
        download_pdf_results = []
        product_links_parsed_data = {}
        try:
            async with semaphore:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    self.logger.info(f"Processing Product Link: {product_links_data_row['link']}")
                    await page.goto(product_links_data_row['link'])
                    await page.wait_for_load_state('domcontentloaded')
                    await page.wait_for_timeout(5000)
                    '''model_title = page.locator(".pipf-product-details-modal__title")
                    model_title_text = await model_title.text_content()
                    self.logger.info(f"Parent Title: {model_title_text}")'''
                    product_name_container = page.locator("xpath=//h1[@class='pipcom-text pipcom-typography-heading-s']")
                    product_name = await product_name_container.text_content()
                    self.logger.info(f"Product Name: {product_name}")
                    containers = page.locator(".pipf-product-details-modal__container")
                    self.logger.info(f"Total Containers: {await containers.count()}")
                    for container_idx in range(await containers.count()):
                        container_header_text = ''
                        instruction_pdf_arr = [] 
                        container = containers.nth(container_idx)
                        # Try to find a header in preceding siblings: h3, h2, or h4
                        header_found = False
                        for tag in ["h3", "h2", "h4"]:
                            header_loc = container.locator(f"xpath=preceding-sibling::{tag}")
                            if await header_loc.count() > 0 :
                                container_header = header_loc.last if await header_loc.count() > 1 else header_loc
                                if await container_header.get_attribute('class') != 'pipf-product-details-modal__document-header':
                                    container_header_text = await container_header.text_content()   
                                header_found = True
                                break
                        
                        if not header_found:
                            self.logger.warning(f"No header found for container {container_idx}")
                        container_children = container.locator("> *")
                        total_container_children = await container_children.count()
                        if total_container_children > 0:
                            text_content_str = ''
                            for child_idx in range(total_container_children):
                                child = container_children.nth(child_idx)
                                tag_name = await child.evaluate("el => el.tagName")
                                if tag_name == 'H2' or tag_name == 'H3' or tag_name == 'H4':
                                    if await child.get_attribute('class') == 'pipf-product-details-modal__document-header':
                                        container_header_text = await child.text_content()
                                else:
                                    if tag_name == 'A':
                                        href = await child.get_attribute('href')
                                        if href and href.endswith('.pdf'):
                                            instruction_pdf_arr.append(href)
                                            self.logger.info(f"Download started for PDF Link => {href} - File Type => {container_header_text}")
                                            download_result = await self.download_instruction_pdf(href,container_header_text,browser,semaphore,product_links_data_row['link'],product_links_data_row['title'],product_name)
                                            if download_result['Download Status'] == 'Success':
                                                self.logger.info(f"PDF File download successful for Product Link => {product_links_data_row['link']} - PDF URL => {href} - File Type => {container_header_text}")
                                                self.logger.info(f"PDF File Downloaded Path => {download_result['pdf_file_path']}")
                                                download_pdf_results.append(download_result)
                                            else:
                                                self.logger.error(f"PDF File download failed for Product Link => {product_links_data_row['link']} - PDF URL => {href} - File Type => {container_header_text}")
                                                download_pdf_results.append(download_result)
                                    else:
                                        # Accumulate all other tags (P, DIV, etc.) in their original order
                                        grand_child = child.locator("> *")
                                        total_grand_child = await grand_child.count()
                                        #self.logger.info(f"Total Grand Children: {total_grand_child}")
                                        if total_grand_child > 0:
                                            for gc_idx in range(total_grand_child):
                                                gc = grand_child.nth(gc_idx)
                                                gc_tag_name = await gc.evaluate("el => el.tagName")
                                                if gc_tag_name == 'A':
                                                    href = await gc.get_attribute('href')
                                                    if href and href.endswith('.pdf'):
                                                        instruction_pdf_arr.append(href)
                                                        download_result = await self.download_instruction_pdf(href,container_header_text,browser,semaphore,product_links_data_row['link'],product_links_data_row['title'],product_name)
                                                        if download_result['Download Status'] == 'Success':
                                                            self.logger.info(f"PDF File download successful for Product Link => {product_links_data_row['link']} - PDF URL => {href} - File Type => {container_header_text}")
                                                            self.logger.info(f"PDF File Downloaded Path => {download_result['pdf_file_path']}")
                                                            download_pdf_results.append(download_result)
                                                        else:
                                                            self.logger.error(f"PDF File download failed for Product Link => {product_links_data_row['link']} - PDF URL => {href} - File Type => {container_header_text}")
                                                            download_pdf_results.append(download_result)
                                                else:
                                                    content = await gc.text_content()
                                                    if content:
                                                        text_content_str = text_content_str + ' \n ' + content.strip()
                                        else:
                                            content = await child.text_content()
                                            if content:
                                                text_content_str = text_content_str + ' \n ' + content.strip()

                            if len(instruction_pdf_arr)>0:
                                self.logger.info(f"Instruction PDFs: {instruction_pdf_arr}")
                                title_text_result.append({'header':container_header_text,'text':text_content_str.strip(),'instruction_pdf':instruction_pdf_arr})
                            else:
                                if len(text_content_str.strip())>0:
                                    title_text_result.append({'header':container_header_text,'text':text_content_str.strip()})
                
                    product_id_containers = page.locator(".pipf-product-identifier")
                    product_id_container = product_id_containers.first
                    product_id_children = product_id_container.locator("> *")
                    product_id_children_count = await product_id_children.count()
                    product_id_text = ''
                    title = ''
                    product_id_value = ''
                    for pid_idx in range(product_id_children_count):
                        product_id_child = product_id_children.nth(pid_idx)
                        if product_id_child is None:
                            continue
                        product_id_text = product_id_text + '-' + (await product_id_child.text_content() or '')
                        if "pipf-product-identifier__label" in str(await product_id_child.get_attribute('class')):
                            title = await product_id_child.text_content() or ''
                        else:
                            if "pipf-product-identifier__value" in str(await product_id_child.get_attribute('class')):
                                product_id_value = await product_id_child.text_content() or ''
                            else:
                                product_id_text = product_id_text + '\n' + (await product_id_child.text_content() or '')
                    
                    if title and product_id_value:
                        title_text_result.append({'header':title,'text':product_id_value.strip()})
                    await browser.close()
            return {'Product Details':title_text_result,'PDF File Details':download_pdf_results}
        except Exception as e:
            #await browser.close()
            self.logger.error(f"Error parsing product links: {product_links_data_row['link']}. Error: \n {e}", exc_info=True)
            return None


    async def download_instruction_pdf(self, pdf_url, container_header_text,browser, semaphore,product_link,title,product_name):
        try:
            async with semaphore:
                # Correctly create and get the download directory path
                download_dir = os.path.join(self.settings.datasource_config.pfdfile_path, container_header_text)
                os.makedirs(download_dir, exist_ok=True)
                
                pdf_file_name = pdf_url.split('/')[-1]
                pdf_file_path = os.path.join(download_dir, pdf_file_name)

                # Use requests to download binary content directly
                # Running in a thread to avoid blocking the event loop
                def fetch_pdf():
                    response = requests.get(pdf_url, stream=True, timeout=30)
                    response.raise_for_status()
                    with open(pdf_file_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return pdf_file_path

                await asyncio.to_thread(fetch_pdf)
                pdf_file_size = os.path.getsize(pdf_file_path)/(1024*1024)
            return {
                    'pdf_file_path': os.path.abspath(pdf_file_path),
                    'pdf_file_name': pdf_file_name,
                    'pdf_file_size': f"{pdf_file_size:.2f} MB",
                    'pdf_file_url': pdf_url,
                    'product_link': product_link,
                    'product_category': title,
                    'product_name': product_name,
                    'pdf_type':container_header_text,
                    'Download Status':'Success'
                }
        except Exception as e:
            self.logger.error(f"Error downloading instruction PDF: {pdf_url}. Error: \n {e}", exc_info=True)
            return {
                'pdf_file_path': None,
                'pdf_file_name': None,
                'pdf_file_size': None,
                'pdf_file_url': pdf_url,
                'product_link': product_link,
                'product_category': title,
                'product_name': product_name,
                'pdf_type':container_header_text,
                'Download Status':'Failed'
            }
    


        