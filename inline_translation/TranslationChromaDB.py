import uuid
import chromadb
from chromadb.config import Settings
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import traceback
from git import Optional

class translation_chromadb_processing :
    def __init__(self, config_data):
        self.config_data = config_data
        self.client = chromadb.PersistentClient(path = config_data['chroma_persist_directory'])
        self.collection = self.client.get_or_create_collection(name = config_data['collection_name'], metadata = {"description":"Collection for storing original paragraph and its translation alongwith correspoding ids"})

    def add_multiple_translations(self, translation_data):
        ids = []
        documents = []
        metadatas = []
        try:
            for data in translation_data:
                translation_id = str(uuid.uuid4())
                ids.append(translation_id)
                documents.append(data['source_text'])
                meta = {
                    "source_language" : data["source_language"],
                    "target_language" : data["target_language"],
                    "translated_text" : data["translated_text"],
                    #"original_text" : data["source_text"],
                    "source_file_name" : data["file_name"],
                    "translated_file_name" : data["translated_filename"],
                    "document_id" : data["document_id"],
                    "paragraph_id" : data["paragraph_id"]
                }
                metadatas.append(meta)
            #print(documents)
            self.collection.add(documents=documents,metadatas=metadatas,ids=ids)
            return ids
        except Exception as e:
            print(f"Error occured while inserting multiple translation data into chroma db. Error : {e}")
            return ids
    
    def get_query_retrieval_output(self, file_name,query_texts:Optional[List[str]]=None,document_id:Optional[str]=None,paragraph_id:Optional[str]=None):
        results = None
        try:
            #print("------------------------------------------ Data from Chroma DB -------------------------------------------")
            if query_texts:
                #print(file_name)
                results = self.collection.query(
                    query_texts=query_texts,
                    #where = {"source_file_name":file_name.split('/')[1]},
                    n_results=1,
                    include=["documents","metadatas","distances"]
                )
                #print(results)
            elif document_id and paragraph_id:
                #print(f"Document id: {document_id}, Paragraph_id: {paragraph_id}")
                results = self.collection.get(
                    where={
                        "$and": [{"document_id": document_id}, {"paragraph_id": paragraph_id}]
                    },
                    include=["documents","metadatas"]
                )
                #print(results)
            else:
                results = self.collection.get(
                    where={
                        "source_file_name":file_name
                    },
                    include=["documents","metadatas"]
                )
            #print(results)
            return  results
            
        except Exception as e:
            print(f"Error occured while retrieving the data from the chroma db for file {file_name}. Error Message: {e}")

    def update_chromadb_translation(self, modify_type, file_name, document_id: Optional[str] = None, paragraph_id: Optional[str] = None, original_text: Optional[str] = None, translated_text: Optional[str]=None, renamed_file_name: Optional[str] = None, translated_renamed_file_name: Optional[str] = None):
        try:
            updated_metadatas = []
            if modify_type == 'modify paragraph':
                document_details = self.get_query_retrieval_output(file_name,None, document_id = document_id,paragraph_id=paragraph_id)
                print("Chromadb details:\n", document_details)
                if document_details['ids']:
                    for metadata in document_details['metadatas']:
                        updated_metadata = metadata.copy()
                        updated_metadata['translated_text'] = translated_text
                        updated_metadatas.append(updated_metadata)
                    print("Updated metadata:", updated_metadatas)   
                    self.collection.update(
                        ids = document_details['ids'],
                        documents=[original_text.replace("\n","").replace("\\","")],
                        metadatas=updated_metadatas
                    )
                    result = self.get_query_retrieval_output(file_name,None, document_id = document_id,paragraph_id=paragraph_id)
                    #print(result) 
                    return result  
            if modify_type == 'renamed file':
                print(file_name)
                translated_new_file_name = renamed_file_name.split(".")[0] + f"_{self.config_data['source_language']}_{self.config_data['target_language']}.{renamed_file_name.split('.')[-1]}"
                print("rename translated file:", translated_new_file_name)
                document_details = self.get_query_retrieval_output(file_name,None,None,None)
                print("Chromadb details:\n", document_details)
                if document_details['ids']:
                    for metadata in document_details['metadatas']:
                        updated_metadata = metadata.copy()
                        updated_metadata['source_file_name'] = renamed_file_name
                        updated_metadata['translated_file_name'] = translated_renamed_file_name
                        updated_metadatas.append(updated_metadata)
                    print("Updated metadata: ", updated_metadatas)
                    self.collection.update(
                            ids=document_details['ids'],
                            metadatas=updated_metadatas
                        )
                    result = self.get_query_retrieval_output(renamed_file_name,None,None,None)
                    #print(result)
                    return result
        except Exception as e:
            print(f"Error occured while updating the record for {file_name} while {modify_type}. Error Message: {e}")
            return None

    def insert_paragraph_between(self, file_name, document_id,new_paragraph, after_paragraph_id,new_translated_paragraph, original_before_paragraph):
        try:
            para_data =[]
            results = self.collection.get(
                where ={
                    "$and":[{"document_id":document_id},{"source_file_name":file_name}]
                }
            )
            if not results['ids']:
                print(f"No paragraphs found for document_id:{document_id}")
            
            for i,unique_id in enumerate(results['ids']):
                metadata_item = results['metadatas'][i]
                para_id = metadata_item.get('paragraph_id')
                #print(metadata_item)
                #print(f"para_id:{para_id}")
                para_data.append({
                    'unique_ids':unique_id,
                    'paragraph_id':para_id,
                    'content':results['documents'][i],
                    'metadata':metadata_item
                })
            #print(para_data)
            for para in para_data:
                #print(f"{para['paragraph_id'][2:]}:{int(para['paragraph_id'][2:])}")
                if int(para['paragraph_id'][2:])>int(after_paragraph_id[2:]):
                    old_para_id = int(para['paragraph_id'][2:])
                    i = old_para_id + 1
                    new_para_id = 'p_' + f"{i:04d}"
                    #print(f"{old_para_id}:{new_para_id}")
                    para['metadata']['paragraph_id'] = new_para_id
                #print(para)
                self.collection.update(ids = [para['unique_ids']],
                    metadatas=[para['metadata']]
                )
            
            # Insert new paragraph
            before_paragraph_query_result = self.get_query_retrieval_output(file_name,original_before_paragraph,document_id = None,paragraph_id=None)
            print(f"Before Paragraph Result: {before_paragraph_query_result}")
            i = int(after_paragraph_id[2:]) + 1
            print("i = ", i)
            new_paragraph_id = 'p_' + f"{i:04d}"
            print("New Paragraph id:", new_paragraph_id)
            print(before_paragraph_query_result['metadatas'][0][0]['translated_file_name'])
            translation_id = str(uuid.uuid4())
            ids = [translation_id]
            new_metadata = {
                "source_language" : self.config_data["source_language"],
                "target_language" : self.config_data["target_language"],
                "translated_text" : new_translated_paragraph,
                "source_file_name" : file_name,
                "translated_file_name" : before_paragraph_query_result['metadatas'][0][0]['translated_file_name'],
                "document_id" : before_paragraph_query_result['metadatas'][0][0]["document_id"],
                "paragraph_id" : new_paragraph_id
            }
            print("New Metadata:", new_metadata)
            self.collection.add(
                ids=ids,
                documents=[new_paragraph],
                metadatas=[new_metadata]
            )
            after_results = self.collection.get(
                where ={
                    "$and":[{"document_id":document_id},{"source_file_name":file_name},
                    {"paragraph_id":{"$in":[after_paragraph_id,new_paragraph_id]}}]
                }
            )
            #print(results)
            return after_results
        except Exception as e:
            print(f"Error occured:{e}")
            print(traceback.format_exc())


    


