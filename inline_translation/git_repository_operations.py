import chromadb
import git
import os
import difflib
import sqlite3
import re
from TranslationChromaDB import *

class git_repository_process:
    def __init__(self, repo_path,config_data):
        self.config_data = config_data
        self.repo_path = repo_path
        self.repo = git.Repo(self.repo_path)
        self.init_sqlite_db()
        self.chroma_obj = translation_chromadb_processing(self.config_data)
    
    def get_sqlite_connection(self):
        return sqlite3.connect(os.path.join(self.config_data['sqlite3_database_folder'],self.config_data['sqlite3_database_name']))

    def init_sqlite_db(self):
        try:
            sql3_conn = self.get_sqlite_connection()
            sql3_cursor = sql3_conn.cursor()
            sql_stmt = f"CREATE TABLE IF NOT EXISTS {self.config_data['sqlite_table_name']} (ID INTEGER PRIMARY KEY AUTOINCREMENT,commit_hash TEXT, file_path TEXT, message TEXT, no_of_objects_commited INTEGER, status TEXT, status_id INTEGER, change_type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            sql3_cursor.execute(sql_stmt)
            sql3_conn.commit()
            sql3_conn.close()
        except Exception as e:
            print(f"Error occured while creating table {self.config_data['sqlite_table_name']} in SQLite3 database {self.config_data['sqlite3_database_name']}. Error Message:{e}")
    
    def create_git_commit_entry(self, commit_hash, file_path, message, no_of_objects_commited,status_id,status_message,change_type):
        try:
            sql3_conn = self.get_sqlite_connection()
            sql3_cursor = sql3_conn.cursor()
            sql_stmt = f"INSERT INTO {self.config_data['sqlite_table_name']} (commit_hash, file_path, message, no_of_objects_commited, status, status_id,change_type) VALUES (?, ?, ?, ?, ?, ?,?)"
            sql3_cursor.execute(sql_stmt, (commit_hash, file_path, message, no_of_objects_commited, status_message,status_id,change_type))
            sql3_conn.commit()
            sql3_conn.close()
            return sql3_cursor.lastrowid
        except Exception as e:
            print(f"Error occured while inserting data in {self.config_data['sqlite_table_name']} table hexsha {commit_hash} and file {file_path}. Erorr Message:{e}")
            return -1

    def check_git_db_commit_status(self,hash_value,file_path):
        git_status = ''
        try:
            sql3_conn = self.get_sqlite_connection()
            sql3_cursor = sql3_conn.cursor()
            sql3_cursor.execute(f"SELECT status from {self.config_data['sqlite_table_name']} where commit_hash = '{hash_value}' and file_path = '{file_path}'")
            git_status = sql3_cursor.fetchone()
            if git_status is not None:
                return git_status[0]
            else:
                return 'No Records found'
        except Exception as e:
            print(f"Error occured while checking the git status for hash {hash_value} for file {file_path}. Error Message: {e}")
            return ''
        finally:
            sql3_conn.close()
    
    def update_git_db_status(self,hash_value, file_path, status,status_id):
        try:
            sql3_conn = self.get_sqlite_connection()
            sql3_cursor = sql3_conn.cursor()
            sql3_cursor.execute(f"UPDATE {self.config_data['sqlite_table_name']} SET status = '{status}', status_id = {status_id} WHERE commit_hash = '{hash_value}' and file_path = '{file_path}'")
            if sql3_cursor.rowcount > 0:
                sql3_conn.commit()
                print(f"Git status updated for git commit {hash_value} for the file {file_path}")
                return True
            else:
                return False
        except Exception as e:
            print(f"Error occured while updating git status in {self.config_data['sqlite_table_name']} table for commit hexsha {hash_value} for file {file_path}. Error Message: {e}")
            return False
        finally:
            sql3_conn.close()

    def get_commit_count(self, branch = 'HEAD'):
        try:
            return sum(1 for commit in self.repo.iter_commits(branch))
        except Exception as e:
            print(f"Error occured while getting the total commit count. Type: {type(e).__name__}, Message: {e}")
            return 0

    def get_commit_details(self, branch='HEAD'):
        #repo = git.Repo(self.repo_path)
        commits = []
        try:
            for commit in self.repo.iter_commits(branch):
                commits.append({
                    "hash": commit.hexsha,
                    "author": commit.author.name,
                    "date": commit.authored_datetime.isoformat(),
                    "message": commit.message.strip(),
                    "no_of_objects_commited":commit.tree.__len__(),
                    "parents":commit.parents
                })
            return commits
        except Exception as e:
            print(f"Error Occured while getting the commit details. Error message: {e}")
            return None

    def _get_tree_contents(self, tree):
        contents = []
        try:
            for entry in tree.traverse():
                if entry.type == 'blob': # It's a file
                    file_content = entry.data_stream.read().decode('utf-8')[:50]
                    contents.append({
                        "path": entry.path,
                        "type": "file",
                        "content": file_content,
                        "hexsha":entry.hexsha
                    })
                elif entry.type == 'tree': # It's a directory
                    contents.append({
                        "path": entry.path,
                        "type": "directory",
                        "contents": [], # Contents will be populated recursively, or left empty if not needed
                        "hexsha":entry.hexsha
                    })
            #print("Tree length:", len(contents))
            return contents
        except Exception as e:
            print(f"Error occured while traversal of commit tree. Error: {e}")


    def get_commit_tree_contents(self, commit_hash=None, branch='HEAD'):
        if commit_hash:
            commit = self.repo.commit(commit_hash)
        else:
            commit = self.repo.commit(branch)
        return self._get_tree_contents(commit.tree)
        
    
    def get_all_commit_details(self, commit_detail):
        commit_content=[]
        try:
            commit = self.repo.commit(commit_detail['hash'])
            parent = commit.parents[0]
            diffs = parent.diff(commit)
            for df in diffs:
                change = {
                    'change_type': df.change_type,
                    'old_file_path': df.a_path,
                    'new_file_path': df.b_path,
                    'commit_sha': commit.hexsha,
                    'message': commit.message.strip(),
                    'is_initial': False,
                    'is_merge': len(commit.parents)>1 
                }
                commit_content.append(change)
            return commit_content
        except Exception as e:
            print(f"Error occured while getting the commit content details for {commit_detail['hash']}. Erorr occured:{e}")
            return []

    def file_history_process(self, commit_entry):
        all_file_diffs = []
        try:
            commits = list(self.repo.iter_commits(paths=[commit_entry['new_file_path']],max_count=5))
            commits = commits[::-1]
            #print("Commits:", commits)
            if not commits:
                print(f"No commits found for {commit_entry['new_file_path']}.")
            for i in range(len(commits)):
                current_commit = commits[i]
                #if i == len(commits)-1 and not current_commit.parents:
                if not current_commit.parents and i==0: #just added
                    file_content = current_commit.tree / commit_entry['new_file_path']
                    all_file_diffs.append({
                        'commit_sha':current_commit.hexsha,
                        'change_type': 'A', # Added
                        'old_file_path': None,
                        'new_file_path': commit_entry['new_file_path'],
                        'diff_content': file_content.data_stream.read().decode('utf-8'),
                        'is_initial': True
                    })
                    continue
                if not current_commit.parents:
                    continue # handle by above code already i..e initl commit scenario
                #print("all_file_diffs:", all_file_diffs)
                parent_commit = current_commit.parents[0]
                #print(f"current_commit:{current_commit}, Parent: {parent_commit}")
                #diff_index = current_commit.diff(parent_commit,paths=[commit_entry['new_file_path']])
                diff_index = parent_commit.diff(current_commit,paths=[commit_entry['new_file_path']])   # Modified as parent diff current line to correct the logic for change_type as D and A
                for diff_obj in diff_index:
                    diff_content_str = ""
                    print("Object Change type:", diff_obj.change_type)
                    if diff_obj.change_type == "M":
                        try:
                            a_blob_content = diff_obj.a_blob.data_stream.read().decode('utf-8') if diff_obj.a_blob else ""
                            #a_blob_content = diff_obj.a_blob.data_stream.read() if diff_obj.a_blob else ""
                        except Exception as e:
                            print(f"Error Message:{e}")
                            a_blob_content=""

                        try:
                            b_blob_content = diff_obj.b_blob.data_stream.read().decode('utf-8') if diff_obj.b_blob else ""
                            #b_blob_content = diff_obj.b_blob.data_stream.read() if diff_obj.b_blob else ""
                        except Exception as e:
                            print(f"Error Message:{e}")
                            b_blob_content=""
                        #if diff_obj.diff:
                            #diff_content_str = diff_obj.diff.decode('utf-8')
                        #diff_content_str =self.repo.git.diff(diff_obj.b_blob.hexsha,diff_obj.a_blob.hexsha)
                        diff_content_str =self.repo.git.diff(diff_obj.a_blob.hexsha,diff_obj.b_blob.hexsha)         # Modified above line to correct the logic for change_type as D and A
                        #print("Diff content string:", diff_content_str)

                    elif diff_obj.change_type == 'A':
                        try:
                            b_blob_content = diff_obj.b_blob.data_stream.read().decode('utf-8') if diff_obj.b_blob else ""
                        except Exception as e:
                            print(f"Error Message:{e}")
                            b_blob_content=""
                        

                        diff_content_str = b_blob_content
                        #print(f"change type:{diff_obj.change_type}, b_blob_content: {diff_content_str}")

                    elif diff_obj.change_type == 'D': # Deleted file
                        try:
                            a_blob_content = diff_obj.a_blob.data_stream.read().decode('utf-8') if diff_obj.a_blob else ""
                            
                        except AttributeError:
                            a_blob_content = ""
                            
                        
                        diff_content_str = f"Deleted content: {a_blob_content}" # Content of the deleted file 
                        
                        #print(f"change type:{diff_obj.change_type}, a_blob_content: {diff_content_str}")

                    all_file_diffs.append({
                        'commit_sha': current_commit.hexsha,
                        'change_type': diff_obj.change_type,
                        'old_file_path': diff_obj.a_path,
                        'new_file_path': diff_obj.b_path,
                        'diff_content': diff_content_str,
                        'is_initial' : False
                    })
            #print(all_file_diffs)
            return all_file_diffs                                          
        except Exception as e:
            print(f"Error occured while fetching the history of the file {commit_entry['new_file_path']}. Error Message:{e}")
            return None
    
    def get_git_file_content_changes(self,file_change_hist,commit_entry):
        formatted_file_change_content={}
        file_header = ''
        index_line = ''
        old_file_marker = ''
        new_file_marker = ''
        hunk_header = []
        context_line = []
        removed_lines = []
        added_lines =[]
        prompt_context_str = '' 
        changed_pairs = []
        minus_line = None
        plus_line = None
        context_line_str = None
        modify_type = ''
        i = 1
        try:
            
            #print(file_change_hist['diff_content'])
            file_change_content = file_change_hist['diff_content'].split('\n')
            for data in file_change_content:
                if data.find('diff --git')!=-1:
                    formatted_file_change_content['file_header'] = data
                if data.find('index') != -1:
                    formatted_file_change_content['index_line'] = data
                if data.find('---') != -1:
                    formatted_file_change_content['old_file_marker'] = data
                if data.find('+++') != -1:
                    formatted_file_change_content['new_file_marker'] = data
                if data.count('@@') >=1:
                    hunk_header.append(data)
                if data.startswith('+') and not data.startswith('+++'):
                    if data.strip() == '+':
                        #prompt_context_str = prompt_context_str + '\\n'
                        continue
                    else: 
                        #prompt_context_str = prompt_context_str.replace("\\","") + '\n' + 'Changed Text: ' + data[1:].replace("\\","") + '\n'
                        i += 1
                        added_lines.append(data)
                        plus_line = data[1:]

                        if minus_line is None:
                            minus_line = context_line_str
                            modify_type = 'added paragraph'
                        else:
                            modify_type = 'modify paragraph'

                        changed_pairs.append((minus_line,plus_line,modify_type))
                        plus_line = None
                        minus_line = None
                if data.startswith('-') and not data.startswith('---'):
                    if data.strip() == '-':
                        #prompt_context_str = prompt_context_str + '\\n'
                        continue
                    else:
                        query_results = self.chroma_obj.get_query_retrieval_output(commit_entry['new_file_path'],query_texts=[data], document_id=None, paragraph_id=None)
                        removed_lines.append((query_results["metadatas"][0][0]['document_id'],query_results["metadatas"][0][0]['paragraph_id'],data))
                        #prompt_context_str = prompt_context_str + data[1:].replace("\\","") + '\n'
                        #prompt_context_str = prompt_context_str + '\n' + 'Original Paragraph ' + query_results["metadatas"][0][0]['translated_text'] + '\n'
                        minus_line = (query_results["metadatas"][0][0]['document_id'],query_results["metadatas"][0][0]['paragraph_id'],data[1:])
                if data.startswith(' '):
                    if data == ' ':
                        #prompt_context_str = prompt_context_str + ' \\n '
                        continue
                    else:
                        if data == '\\n':
                            continue
                        else:
                            query_results = self.chroma_obj.get_query_retrieval_output(commit_entry['new_file_path'],query_texts=[data], document_id=None, paragraph_id=None)
                            context_line.append((query_results["metadatas"][0][0]['document_id'],query_results["metadatas"][0][0]['paragraph_id'],data))
                            context_line_str = (query_results["metadatas"][0][0]['document_id'],query_results["metadatas"][0][0]['paragraph_id'],data[1:])
                            #prompt_context_str =prompt_context_str + '\n' + self.config_data['source_language'] + ' -> ' + data.replace(r"\\","") + '\n'
                            #prompt_context_str = prompt_context_str + '\n' + self.config_data['target_language'] + ' -> ' + query_results["metadatas"][0][0]['translated_text'] + '\n'
            #prompt_context_str = prompt_context_str + '\n' + f"Translate all the changed texts above from {self.config_data['source_language']} to {self.config_data['target_language']} and rebuilt the paragraphs only without any additional text, explanations and comments."
            #print(prompt_context_str)
            #formatted_file_change_content['prompt_context_string'] = prompt_context_str
            formatted_file_change_content['hunk_header'] = hunk_header
            formatted_file_change_content['context_line'] = context_line
            formatted_file_change_content['added_lines'] = added_lines
            formatted_file_change_content['removed_lines'] = removed_lines
            formatted_file_change_content['file_name'] = commit_entry['new_file_path']
            formatted_file_change_content['changed_pairs'] = changed_pairs
            #print("------------------------------------------------- Formatted File Content Changes ------------------------------------------------------")
            #print(formatted_file_change_content)
            #print(formatted_file_change_content['prompt_context_string'])
            return formatted_file_change_content
        except Exception as e:
            print(f"Error occured while processing the file changes for {file_change_hist['new_file_path']}. Error Message: {e}")

    
    
    