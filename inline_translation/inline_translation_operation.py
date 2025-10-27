import yaml
from git_repository_operations import *
from file_translation_process import *
from TranslationChromaDB import *
import traceback

class inline_translation:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
    
    def read_yaml_file(self):
        with open(self.config_file_path, 'r') as file:
            data = yaml.safe_load(file)
        return data

    def write_document_id_value_to_file(self, doc_id):
        print("Last processed document id:", doc_id)
        with open('document_id.txt','w') as f:
            f.write(f"Document_id:{doc_id}")
    
    def read_document_id_value_to_file(self):
        file_doc_id = ''
        with open('document_id.txt','r') as f:
            file_doc_id = f.read()
        return file_doc_id
        

if __name__ == '__main__':
    config_file_path = 'config.yml'
    try:
        inline_translation_obj = inline_translation(config_file_path)
        config_data = inline_translation_obj.read_yaml_file()
        print(config_data['repo_path'])
        git_proc = git_repository_process(config_data['repo_path'],config_data)
        print("Total Git commit:", git_proc.get_commit_count())
        commit_details = git_proc.get_commit_details()
        print(commit_details[::-1])
        trans = file_translation(commit_details,config_data)
        chromadb_obj = translation_chromadb_processing(config_data)
        all_commit_details = []
        doc_id = 0
        doc_line = inline_translation_obj.read_document_id_value_to_file()
        if len(doc_line)>1:
            doc_id = int(doc_line.replace("Document_id:",''))
            print("Document_id from file:", doc_line.replace("Document_id:",''))

        for commit_detail in commit_details[::-1]:
            if not commit_detail['parents']:
                print("\nInitial Commit...\n")
                commit_content = git_proc.get_commit_tree_contents(commit_detail['hash'])
                print(commit_content)
                for item in commit_content:
                    if item['type'] == 'file':
                        #doc_id = doc_id + 1
                        git_db_status = git_proc.check_git_db_commit_status(commit_detail['hash'],item['path'])
                        print("Git Status:", git_db_status)
                        if git_db_status == '' or git_db_status is None or git_db_status == 'No Records found':
                            doc_id = doc_id + 1
                            git_entry_id = git_proc.create_git_commit_entry(commit_detail['hash'],item['path'],commit_detail['message'],commit_detail['no_of_objects_commited'],0,'In-progress','initial_commit')
                            if git_entry_id == -1:
                                print(f"Error occured while inserting data in {config_data['sqlite_table_name']} table hexsha {commit_detail['hash']} and file {item['path']}")
                            else:
                                print(f"Data inserted successfully with id: {git_entry_id}....")
                            file_translation_data_ids = trans.files_initial_processing(doc_id,commit_detail, item, 'initial_commit')
                            if len(file_translation_data_ids) > 0:
                                git_proc.update_git_db_status(commit_detail['hash'],item['path'],'Completed',1)
                                inline_translation_obj.write_document_id_value_to_file(doc_id)
                            else:
                                git_proc.update_git_db_status(commit_detail['hash'],item['path'],'Failed',-1)
                        if git_db_status.lower() == 'completed':
                            print(f"File {item['path']} translation process is already completed...")
            else:
                commit_detail_content = git_proc.get_all_commit_details(commit_detail)
                for item in commit_detail_content:
                    all_commit_details.append(item)
        print("\nGit commit component details.....\n")
        print(all_commit_details)
        print("Document id after initial Commit:", doc_id)
        for commit_entry in all_commit_details:
            print(f"\nGet the commit history for the file {commit_entry['new_file_path']}\n")
            diff_content = git_proc.file_history_process(commit_entry)
            print("================================================= File Commit History =================================================================\n")
            file_history_content = diff_content[::-1]
            #print(f"File history content: {file_history_content}")
            for hist in file_history_content:
                if hist['change_type'] == 'A':
                    #print(commit_entry['change_type'])
                    git_db_status = git_proc.check_git_db_commit_status(hist['commit_sha'],hist['new_file_path'])
                    print(f"Git Status: {git_db_status.lower()}, Hash Value: {hist['commit_sha']}, File: {hist['new_file_path']}, Change_type: {hist['change_type']}")
                    if git_db_status.lower() == 'completed':
                        print("File translation already completed...")
                    else:
                        if git_db_status.lower() == 'no records found' or git_db_status.strip() == '':                         
                            git_entry_id = git_proc.create_git_commit_entry(hist['commit_sha'],hist['new_file_path'],commit_entry['message'],1,0,'In-progress',hist['change_type'])
                        elif git_db_status.lower() == 'failed':
                            git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'In-progress',0)
                        else:
                            print(f"Invalid git commit status for hash {hist['commit_sha']} and file {hist['new_file_path']}.")
                        print("Commit Change Type:", commit_entry['change_type'])
                        if commit_entry['change_type']!='R': 
                            print(hist)
                            message = trans.new_added_file_processing(commit_entry,hist)
                            print("Message New file:", message)
                            print(message.lower().find('success'))
                            if message.lower().find('success')>=0:
                                doc_id = int(message.split(":")[-1].strip())
                                print(f"Current Document id: {doc_id}")
                                inline_translation_obj.write_document_id_value_to_file(doc_id)
                                git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Completed',1)
                            elif message.lower().find('failed')>=0:
                                git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Failed',-1)
                            else:
                                print(f"Git commit status not updated for hash {hist['commit_sha']} for file {hist['new_file_path']}")
                        else:
                            print("Old file:", hist['old_file_path'])
                            print(f"File {hist['new_file_path']} is renamed so the data already exists in the system. No processing is required except change in file name wherever applicable.")
                            #print(f"Commit details: {commit_entry}")
                            translated_old_file_name = commit_entry['old_file_path'].split('/')[1].split('.')[0] + "_" + config_data['source_language'] + '_' + config_data['target_language'] + '.txt'
                            translated_new_file_name = commit_entry['new_file_path'].split('/')[1].split('.')[0] + "_" + config_data['source_language'] + '_' + config_data['target_language'] + '.txt'
                            query_result = chromadb_obj.update_chromadb_translation('renamed file',commit_entry['old_file_path'].split('/')[1],None,None,None,None,commit_entry['new_file_path'].split('/')[1],translated_new_file_name)
                            #print(f"Renamed file Chroma Db details:\n {query_result}")
                            msg = trans.rename_file_to_translate(translated_old_file_name,translated_new_file_name)
                            if msg.lower() == 'success':
                                git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Completed',1)
                            else:
                                git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Failed',1)
                if hist['change_type'] == 'D':
                    git_db_status = git_proc.check_git_db_commit_status(hist['commit_sha'],hist['old_file_path'])
                    print(f"Git Status: {git_db_status.lower()}, Hash Value: {hist['commit_sha']}, File: {hist['new_file_path']}, Change_type: {hist['change_type']}")
                    if git_db_status.lower() == 'completed':
                        print("File translation already completed...")
                if hist['change_type'] == 'M':
                    git_db_status = git_proc.check_git_db_commit_status(hist['commit_sha'],hist['new_file_path'])
                    print(f"Git Status: {git_db_status.lower()}, Hash Value: {hist['commit_sha']}, File: {hist['new_file_path']}, Change_type: {hist['change_type']}")
                    if git_db_status.lower() == 'completed':
                        print("File translation already completed...")
                    elif git_db_status.lower() == 'no records found' or git_db_status.strip() == '':
                        git_entry_id = git_proc.create_git_commit_entry(hist['commit_sha'],hist['new_file_path'],commit_entry['message'],1,0,'In-progress',hist['change_type'])
                        file_content_change_details = git_proc.get_git_file_content_changes(hist,commit_entry)
                        #print(file_content_change_details)
                        print(file_content_change_details['changed_pairs'])
                        message = trans.file_changes_history_process(file_content_change_details)
                        if message.lower == 'success':
                            git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Completed',1)
                        else:
                            git_proc.update_git_db_status(hist['commit_sha'],hist['new_file_path'],'Failed',1)
                    else:
                        print("Not a valid git status....")
        inline_translation_obj.write_document_id_value_to_file(doc_id)       
    except Exception as e:
        print(f"Error occured:{e} \n")
        print(traceback.format_exc())



   
