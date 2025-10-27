import os
import re
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
from nltk.tokenize import sent_tokenize
import difflib
import pandas as pd

try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    nltk.download('punkt')

from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnableParallel, RunnablePassthrough
from TranslationChromaDB import *
from langchain_anthropic import ChatAnthropic

# Prompt templates
from langchain.prompts import (
    ChatPromptTemplate, 
    PromptTemplate, 
    FewShotPromptTemplate,
    MessagesPlaceholder
)

# Memory
from langchain.memory import (
    ConversationBufferMemory, 
    ConversationSummaryMemory,
    ConversationBufferWindowMemory
)

# Chains
from langchain.chains import (
    LLMChain, 
    ConversationChain, 
    RetrievalQA,
    StuffDocumentsChain,
    MapReduceDocumentsChain
)


class file_translation:
    def __init__(self,commit_detail,config_data):
        self.commit_detail = commit_detail
        self.config_data = config_data
        self.llm = OllamaLLM(
            model = config_data["llm_model"],
            base_url = config_data["base_url"],
            temperature = 0.1
        )
        self.claude_llm = ChatAnthropic(
            model = self.config_data['claude_llm_model'],
            temperature= 0.7,
            max_tokens = 1024,
            anthropic_api_key = self.config_data['anthropic_api_key']
        )
        self.chroma_obj = translation_chromadb_processing(self.config_data)
    
    def file_changes_history_process(self, file_content_change_details):
        #text_split_list = []
        try:
            text_split_list = []
            #chroma_obj = translation_chromadb_processing(self.config_data)
            for pair in file_content_change_details['changed_pairs']:
                if pair[2].lower() == 'modify paragraph':
                    print("------------------------------------ Changed Data ------------------------------------")
                    changed_data = self.get_changed_sentence_manually(pair[0][2],pair[1]) 
                    #print(changed_data)
                    text_split_list = self.get_changed_text_split(changed_data,pair)
                    #print(text_split_list)
                    print("------------------------------ Prompt template-----------------------")
                    prompt_str = self.get_prompt_template(text_split_list, file_content_change_details['file_name'], pair[0][0], pair[0][1])
                    print(file_content_change_details['file_name'].split('/')[1])
                    print(prompt_str)
                    old_data_result = self.chroma_obj.get_query_retrieval_output(file_content_change_details['file_name'].split('/')[1], query_texts= None, document_id= pair[0][0],paragraph_id = pair[0][1])
                    print("Old Data ChromaDB details:", old_data_result)
                    prompt_result = self.translate_content(prompt_str,'modify paragraph')
                    print(prompt_result['text'])
                    modify_data_query_result = self.chroma_obj.update_chromadb_translation('modify paragraph',file_content_change_details['file_name'].split('/')[1],document_id=pair[0][0],paragraph_id=pair[0][1],original_text=pair[1],translated_text=prompt_result['text'],renamed_file_name=None,translated_renamed_file_name=None)
                    print(modify_data_query_result)
                    modified_translated_file_data = self.get_modified_translated_file_data(old_data_result,modify_data_query_result, pair, file_content_change_details['file_name'])
                    print("Total Modified File records:", len(modified_translated_file_data))
                    if len(modified_translated_file_data)>0:
                        file_split_char = self.get_paragraph_split_character(os.path.join(self.config_data['translated_file_folder'],old_data_result['metadatas'][0]['translated_file_name']))
                        print("File Split Character:", file_split_char)
                        if file_split_char is not None:
                            message = self.write_modified_translated_file(os.path.join(self.config_data['translated_file_folder'],old_data_result['metadatas'][0]['translated_file_name']),modified_translated_file_data,file_split_char)
                            print(message)
                            return message
                    print("------------------------------------ Changed Data ------------------------------------")
                if pair[2].lower() == 'added paragraph':
                    text_split = {
                        'before_text': pair[0][2],
                        'changed_text':pair[1],
                        'after_text':''
                    }
                    text_split_list.append(text_split)
                    #print(prompt_str)
                    prompt_str = self.get_prompt_template(text_split_list, file_content_change_details['file_name'], pair[0][0], pair[0][1])
                    print("Prompt String:", prompt_str)
                    print(file_content_change_details['file_name'].split('/')[1])
                    prompt_result = self.translate_content(prompt_str,'added paragraph')
                    print(f"\n{prompt_result['text']}")
                    if len(re.findall("\n\n",prompt_result['text']))>1:
                        split_char = "\n\n"
                    elif len(re.findall("\n",prompt_result['text']))>1:
                        split_char = "\n"
                    else:
                        print("Empty Separator.")
                    print("Split Character:", split_char)
                    translated_new_paragraph = [p for p in prompt_result['text'].split(split_char) if p]
                    print("New Paragraph:", translated_new_paragraph)
                    upsert_paragraphs_chroma_details = self.chroma_obj.insert_paragraph_between(file_content_change_details['file_name'].split('/')[1], pair[0][0],pair[1], pair[0][1],translated_new_paragraph[1],pair[0][2])
                    print(upsert_paragraphs_chroma_details)
                    #query_result = self.chroma_obj.get_query_retrieval_output(file_content_change_details['file_name'].split('/')[1],query_texts=None,document_id=None,paragraph_id=None)
                    #print("Query Output\n", query_result)
                    added_paragraph_translated_data = self.get_added_paragraph_translated_file_data(upsert_paragraphs_chroma_details)
                    if len(added_paragraph_translated_data)>0:
                        file_split_char = self.get_paragraph_split_character(os.path.join(self.config_data['translated_file_folder'], upsert_paragraphs_chroma_details['metadatas'][0]['translated_file_name']))
                        if file_split_char is not None:
                            message = self.write_modified_translated_file(os.path.join(self.config_data['translated_file_folder'], upsert_paragraphs_chroma_details['metadatas'][0]['translated_file_name']),added_paragraph_translated_data,file_split_char)
                            print(message)
                            return message
        except Exception as e:
            print(f"Error occured when formatting the prompt for translation of file {file_content_change_details['file_name']}. Error Message: {e}")
            return 'Failed'
    
    def get_added_paragraph_translated_file_data(self, upsert_paragraphs_chroma_details):
        try:
            original_file_path = os.path.join(self.config_data['file_path_to_translate'], upsert_paragraphs_chroma_details['metadatas'][0]['source_file_name'])
            translated_file_path = os.path.join(self.config_data['translated_file_folder'], upsert_paragraphs_chroma_details['metadatas'][0]['translated_file_name'])
            new_paragraph_id = upsert_paragraphs_chroma_details['metadatas'][1]['paragraph_id']
            pid = int(new_paragraph_id[2:])
            with open(translated_file_path,'r', encoding='utf-8') as trans_file:
                file_content = trans_file.read()
            if len(re.findall("\n\n",file_content))>1:
                split_char = "\n\n"
            elif len(re.findall("\n",file_content))>1:
                split_char = "\n"
            else:
                print("Invalid split character. Not able to read the translated file.")
            paragraphs = file_content.split(split_char)
            print("Before List Insertion Length:", len(paragraphs))
            paragraphs.insert(pid,upsert_paragraphs_chroma_details['metadatas'][1]['translated_text'])
            #print("\n".join([f'{i}:{paragraphs[i]}' for i in range(len(paragraphs))]))
            print("After Addition in list Length:", len(paragraphs))
            return paragraphs
        except Exception as e:
            print(f"Error occured while reading the translated file for added paragraph translation. Error Message: {e}")
            print(traceback.format_exc())
            return []

    
    def write_modified_translated_file(self,translated_file_path,modified_translated_file_data,file_split_char):
        try:
            with open(translated_file_path, 'w', encoding='utf-8') as f:
                f.write(file_split_char.join(modified_translated_file_data))
            print("✓ File written successfully")
            return 'Success'
        except PermissionError:
            print(f"✗ Permission denied: Cannot write to {translated_file_path} file")
            return 'Failed'
        except FileNotFoundError:
            print(f"✗ Directory not found at the path {translated_file_path}")
            return 'Failed'
        except IOError as e:
            print(f"✗ IO Error occurred for the file {translated_file_path} : {e}")
            return 'Failed'
        except Exception as e:
            print(f"✗ Unexpected error occured for the {translated_file_path} file: {e}")
            return 'Failed'
        finally:
            print("Write operation completed")


    def get_modified_translated_file_data(self,old_data_result,modify_data_query_result, pair, files_to_translate):
        split_char = ''
        try:
            print(os.path.join(self.config_data['translated_file_folder'],old_data_result['metadatas'][0]['translated_file_name']))
            with open(os.path.join(self.config_data['translated_file_folder'],old_data_result['metadatas'][0]['translated_file_name']),'r', encoding='utf-8') as trans_file:
                file_content = trans_file.read()
                print(len(file_content))
            if len(re.findall("\\n\\n",file_content))>1:
                split_char = "\n\n"
            elif len(re.findall("\\n",file_content))>1:
                split_char = "\n"
            else:
                print("Invalid split character. Not able to read the translated file.")
            paragraphs = file_content.split(split_char)
            print("Line:", modify_data_query_result['metadatas'][0]['translated_text'])
            new_translate_file_data = [modify_data_query_result['metadatas'][0]['translated_text'].replace("\n","").replace("\\","") if para == old_data_result['metadatas'][0]['translated_text'] else para for para in paragraphs]
            print("New Translated Data:", new_translate_file_data)
            return new_translate_file_data
        except Exception as e:
            print(f"Error occured while retrieving the translated data of source file {files_to_translate.split('/')[1]}. Error Message: {e}")
            return []

    def get_changed_text_split(self,changed_data,pair):
        text_split = {}
        text_split_list = []
        after_change_sent_list = []
        changed_text_sent_list = []
        str = ''
        after_flg = 0
        try:
            str_type = 'before'
            change_typ = ''
            change_idx = 0
            idx = 0
            changed_str = ''
            after_paragraph_sent = sent_tokenize(pair[1])
            for i, para in enumerate(after_paragraph_sent):
                after_change_sent_list.append((i,pair[1].index(para),len(para),para))
            for d1 in changed_data:
                for k,v in d1.items():
                    if k == 'inserted':
                        for i,val in enumerate(v):
                            changed_text_sent_list.append((k,pair[1].index(val),len(val),val))
                    elif k == 'replaced_to':
                        for val in enumerate(v):
                            changed_text_sent_list.append((k,pair[1].index(val),len(val),val))
            after_change_sent_pd = pd.DataFrame(after_change_sent_list,columns = ['sentence_order','start_index','sentence_length','sentence'])
            changed_text_sent_pd = pd.DataFrame(changed_text_sent_list,columns = ['change_type','start_index','sentence_length','sentence'])
            df = after_change_sent_pd.merge(changed_text_sent_pd, how = 'left', on =['start_index','sentence_length','sentence'])
            df['change_type'] = df['change_type'].fillna('')
            #print(df)
            for index, row in df.iterrows():
                #print(row['sentence'])
                #print(text_split)
                if idx == row['start_index']:
                    if row['change_type'] == change_typ and row['change_type'] not in ['inserted','replaced_to']:
                        str = str + row['sentence']
                    else:
                        if row['change_type'] in ['inserted','replaced_to']:
                            change_typ = row['change_type']
                            if change_idx <= row['start_index'] and len(changed_str)==0:
                                text_split[str_type + '_text'] = str
                                change_idx = row['start_index']
                                str = ''
                            if after_flg == 1:
                                text_split_list.append(text_split)
                                #print(text_split_list)
                                after_flg = 0
                                #print(text_split)
                                text_split = {}
                                str = ''
                            changed_str = changed_str + row['sentence']
                            change_idx = change_idx + row['sentence_length']+1                        
                        else:
                            #print(f"Changed index:{change_idx} ,rowstart_index: {row['start_index']}")
                            if row['start_index'] == change_idx and len(changed_str)>0:
                                #print("Changed Text:", changed_str)
                                text_split['changed_text'] = changed_str
                                str_type = 'after'
                                str = str + row['sentence']
                                changed_str = ''
                                change_typ = row['change_type']
                                after_flg = 1
                    idx = idx + row['sentence_length'] + 1
            if len(changed_str)>0:
                text_split['changed_text'] = changed_str
                text_split_list.append(text_split)
                changed_str = ''

            if len(str)>0:
                text_split['after_text'] = str
                text_split_list.append(text_split)
                str = ''
            #print(text_split_list)
            return text_split_list
        except Exception as e:
            print(f"Error occured while getting the changed text split. Error Message: {e}")
            return None

    def get_prompt_template(self, text_split_list,file_name, document_id, paragraph_id):
        prompt_str = ''
        try:
            #chromadb_obj = translation_chromadb_processing(self.config_data)
            for text_split in text_split_list:
                query_result = self.chroma_obj.get_query_retrieval_output(file_name, query_texts= None, document_id= document_id,paragraph_id = paragraph_id)
                #print(query_result['metadatas'][0]['translated_text'])
                if 'before_text' in text_split:
                    prompt_str = prompt_str + f"before text: {text_split['before_text']} \n\nChanged Text: {text_split['changed_text']} \n\n"
                else:
                    prompt_str = prompt_str + f"before text: \n\nChanged Text: {text_split['changed_text']} \n\n"
                if 'after_text' in text_split:
                    prompt_str = prompt_str + f"after text: {text_split['after_text']} \n\n"
                else:
                    prompt_str = prompt_str + f"after text: \n\n"
            prompt_str = prompt_str + f"Original paragraph: {query_result['metadatas'][0]['translated_text']}"
            return prompt_str
        except Exception as e:
            print(f"Error occured while forming the prompt template for {file_name}, document_id: {document_id} and paragraph_id: {paragraph_id}. Error Message: {e}")
            return prompt_str
 
    def files_initial_processing(self, doc_id,commit_detail_item, commit_content_item = None,commit_type = None):
        file_translation_data_ids = []
        try:
            
            if commit_type == 'initial_commit':
                file_to_translate = os.path.join(self.config_data['repo_path'],commit_content_item['path'])
            else:
                file_to_translate = os.path.join(self.config_data['repo_path'],
                commit_detail_item['new_file_path'] if commit_detail_item['new_file_path'] is not None or commit_detail_item['new_file_path'].strip() != '' else commit_detail_item['old_file_path'])
            #print("File to translate:", file_to_translate)
            document_id = "doc_" + f"{doc_id:04d}" 
            with open(file_to_translate,'r') as file:
                file_content = file.read()
                if len(re.findall("\n\n",file_content))>1:
                    print("Paragraph file:", file_to_translate)
                    split_char = "\n\n"
                    file_translation_data = self.source_file_translation_process(file_to_translate,file_content,"initial_commit",document_id,"\n\n")
                    #print("Translation Data:", file_translation_data)
                    translation_ids = self.chroma_obj.add_multiple_translations(file_translation_data)
                    file_translation_data_ids.append(translation_ids)
                elif len(re.findall("\n",file_content))>1:
                    print("New Line file:", file_to_translate)
                    split_char = "\n"
                    file_translation_data = self.source_file_translation_process(file_to_translate,file_content,"initial_commit",document_id,"\n")
                    #print("Translation Data:", file_translation_data)
                    translation_ids = self.chroma_obj.add_multiple_translations(file_translation_data)
                    file_translation_data_ids.append(translation_ids)
                else:
                    print("File contains unknown Splitting character.................")
                    file_translation_data = []
                print("Total paragraphs/lines to write:", len(file_translation_data))
                total_records = self.translated_data_file_processing(file_translation_data,file_to_translate,split_char)   
                if total_records>0:
                    print(f"Translated File {file_to_translate} is processed successfully.")
                    return file_translation_data_ids
                else:
                    print(f"Error occured while writing the translated file {file_to_translate}.")
                    return []
        except Exception as e:
            print(f"Error occured while processing the file. Error Message: {e}")
            return []
    
    def source_file_translation_process(self, file_path,file_content,commit_type,document_id,split_char):
        file_translate_content = []
        try:
            i = 0
            #print(split_char)
            paragraphs = file_content.split(split_char)
            print("Total Paragraphs in file content:", len(paragraphs))
            file_path_arr = file_path.split("/")
            file_name = file_path_arr[-1]
            print(f"File under process:{file_name}")
            for para in paragraphs:
                para_dict = {}
                i +=1
                source_text= para.replace("\n","").replace("\\","")
                #source_text= para
                result = self.translate_content(source_text,commit_type)
                for k, v in result.items():
                    if k == 'text':
                        para_dict["translated_text"] = v.replace("\n","").replace("\\","")
                    else:
                        para_dict[k] = v.replace("\n","").replace("\\","")
                para_dict['file_name'] = file_name
                para_dict['translated_filename'] = file_name.split('.')[0] + f"_{self.config_data['source_language']}_{self.config_data['target_language']}.{file_name.split('.')[-1]}"
                para_dict['document_id'] = document_id
                para_dict['paragraph_id'] = 'p_' + f"{i:04d}"
                file_translate_content.append(para_dict)
            #print(file_translate_content)
            return file_translate_content
        except Exception as e:
            print(f"Error occured while translation paragraph based file {file_path}. Error occured: {e}")
            return file_translate_content
 
    def translate_content(self, para,commit_type):
        try:
            if commit_type == "initial_commit" or commit_type == "new_file_added":
                prompt = PromptTemplate(
                    input_variables = ["source_language","target_language","source_text"],
                    template = """Translate the following text from {source_language} to {target_language}. 

                    Provide only the translation without any additional text, explanation, formatting, suffixes or prefixes. 

                    Source text: {source_text}
                    """
                )
                llm_chain = LLMChain(llm=self.llm, prompt=prompt)
                result = llm_chain.invoke({"source_language":self.config_data["source_language"],"target_language":self.config_data["target_language"],"source_text":para})
            if commit_type == "modify paragraph":
                #print(para)
                prompt = PromptTemplate(
                    input_variables = ["source_language","target_language","prompt_text"],
                    template = """
                    {prompt_text}

                    Original paragraph denotes a translation of article and the before and after represents the original article - 
                    please translate changed line from {source_language} to {target_language} maintaining the original paragraph as it is and appending
                    only the lines which have been changed. Provide updated full paragraph after change. No additional text, summary, comments, explanation.
                    Critical Rule: The sentence order must be: [Before Text] + [Changed Text] + [After Text]. No exceptions, no narrative improvements, no logical reordering.
                    
                    """
                )
                llm_chain = LLMChain(llm=self.claude_llm, prompt=prompt)
                result = llm_chain.invoke({"source_language":self.config_data["source_language"],"target_language":self.config_data["target_language"],"prompt_text":para})
                print(result)
            if commit_type == 'added paragraph':
                prompt = PromptTemplate(
                    input_variables = ["source_language","target_language","prompt_text"],
                    template = """
                    {prompt_text}

                    Original paragraph denotes a translation of article and the before and after represents the original article - 
                    please translate changed line from {source_language} to {target_language} maintaining the original paragraph as it is and create a separate paragraph for
                    only the line which has changed. Provide updated full paragraph only after change. No additional text, summary, comments, explanation. 
                    Critical Rule: Maintain the original paragraph as it is before the changed paragraph. No exceptions, no narrative improvements, no logical reordering.
                    
                    """
                )
                llm_chain = LLMChain(llm=self.claude_llm, prompt=prompt)
                result = llm_chain.invoke({"source_language":self.config_data["source_language"],"target_language":self.config_data["target_language"],"prompt_text":para})
                print(result)
            return result 
        except Exception as e:
            print(f"Error occured while translating content \n {para} \n from {self.config_data['source_language']} to {self.config_data['target_language']}. Error occured: {e}")
            return None
    
    def translated_data_file_processing(self,file_translation_data,source_file_path,split_char):
        source_file_linecount = 0
        try:
            if not os.path.exists(os.path.join(self.config_data['translated_file_folder'],file_translation_data[0]['translated_filename'])):
                with open(os.path.join(self.config_data['translated_file_folder'],file_translation_data[0]['translated_filename']),'w',encoding = "utf-8") as f:
                    for data in file_translation_data:
                        #f.write(data['translated_text'].replace("\\n\\n","").replace("\\",""))
                        f.write(data['translated_text'])
                        f.write(split_char)
                        source_file_linecount = source_file_linecount + 1
                print(f"Source file Line Count:", source_file_linecount)
            
            with open(os.path.join(self.config_data['translated_file_folder'],file_translation_data[0]['translated_filename']),'r') as trans_file:
                lines = trans_file.readlines()
                print(len(lines))
                return len(lines)
        except Exception as e:
            print(f"Error occured while writing translated data for {file_translation_data[0]['translated_filename']}. Error Message: {e}")
            return 0

    def get_changed_sentence_manually(self, before_text, after_text):
        changed_text = []
        try:
            before_sents = sent_tokenize(before_text)
            after_sents = sent_tokenize(after_text)
            sm = difflib.SequenceMatcher(None, before_sents, after_sents)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    #print(f"✓ Lines {i1}-{i2} and {j1}-{j2} are equal")
                    continue
                elif tag == 'delete':
                    changed_text.append({"deleted":before_sents[i1:i2]})
                elif tag == 'insert':
                    changed_text.append({"inserted":after_sents[j1:j2]})
                elif tag == 'replace':
                    changed_text.append({"replaced_from":before_sents[i1:i2],"replaced_to":after_sents[j1:j2]})
            #print(changed_text)
            return changed_text     
        except Exception as e:
            print(f"Error occured while getting the changed sentence between the before and after text. Error Message: {e}")
            return []
    
    
    def get_new_translation_data(self, document_id, new_paragraph_id, new_original_paragraph, new_translated_paragraph):
        try:
            pass
        except Exception as e:
            print(f"Error occured while forming the translation data record for document_id: {document_id} and new paragraph_id: {new_paragraph_id}. Error Message: {e}")
    

    def new_added_file_processing(self, commit_entry, hist):
        file_translation_data = []
        split_char= ''
        file_name = ''
        file_content = ''
        try:
            file_path = hist['new_file_path'] if hist['new_file_path'] is not None or hist['new_file_path'].strip() != '' else hist['old_file_path']
            #print("Old file path:", hist['old_file_path'])
            #print("New file path:", hist['new_file_path'])
            if hist['new_file_path'] is not None or hist['new_file_path'].strip() != '':
                file_name = hist['new_file_path'].split('/')[1]
            else:
                file_name = hist['old_file_path'].split('/')[1]
            print(f"file Name: {file_name}")
            file_to_translate = str(os.path.join(self.config_data['repo_path'],
                hist['new_file_path'] if hist['new_file_path'] is not None or hist['new_file_path'].strip() != '' else hist['old_file_path']))
            print(file_to_translate)
            if os.path.exists(file_to_translate):
                print("File exists")
                with open(file_to_translate,'r') as file:
                    file_content = file.read()
                if len(re.findall("\n\n",file_content))>1:
                    print("Paragraph file:", file_to_translate)
                    split_char = "\n\n"
                elif len(re.findall("\n",file_content))>1:
                    print("New Line file:", file_to_translate)
                    split_char = "\n"
                print(file_content.split(split_char)[0])
                query_result = self.chroma_obj.get_query_retrieval_output(file_name,file_content.split(split_char)[0],document_id=None,paragraph_id=None)
                #print("Query Result:", query_result)
                if query_result['distances'][0][0]>0.0:
                    with open('document_id.txt','r') as f:
                        file_doc_id = f.read()
                    if len(file_doc_id)>1:
                        doc_id = int(file_doc_id.replace("Document_id:",'')) + 1
                        document_id = "doc_" + f"{doc_id:04d}"
                        print("Document_id from file:", document_id)
                    file_translate_content = self.source_file_translation_process(file_path,file_content,"new_file_added",document_id,split_char)
                    print(f"Translation Content: {len(file_translate_content)}")
                    translation_ids = self.chroma_obj.add_multiple_translations(file_translate_content)
                    if len(translation_ids)>0:
                        print("File data is inserted in chromadb successfully...")
                        total_records = self.translated_data_file_processing(file_translate_content,file_to_translate,split_char)
                        return 'Success: ' + str(doc_id)
                else:
                    print(f"The file {file_name} is renamed.")
                    return 'Rename File'
            else:
                print("File does not exists")         
                return 'Failed'
        except Exception as e:
            print(f"Error occured while processing newly added text file {hist['new_file_path']}. Error Message: {e}")
            return 'Failed'
    

    def get_paragraph_split_character(self,file_path):
        try:
            with open(file_path,'r',encoding='utf-8') as file:
                file_content = file.read()
            if len(re.findall("\n\n",file_content))>1:
                split_char = "\n\n"
            elif len(re.findall("\n",file_content))>1:
                split_char = "\n"
            else:
                print("File contains unknown Splitting character.................")
            print("Split Char:", split_char)
            return split_char
        except Exception as e:
            print(f"Error occured while reading the translated file on the location {file_path}. Error essage: {e}")
            return None
        
    def rename_file_to_translate(self,translated_old_file_name,translated_new_file_name):
        try:
            os.rename(os.path.join(self.config_data['translated_file_folder'],translated_old_file_name),os.path.join(self.config_data['translated_file_folder'],translated_new_file_name))
            return 'success'
        except FileNotFoundError:
            print(f"Error: The file '{translated_old_file_name}' was not found.")
            return 'failed'
        except Exception as e:
            print(f"An error occurred: {e}")
            return 'failed'
