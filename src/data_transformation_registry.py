from __future__ import annotations
from typing import Callable,Any
from pathlib import Path
import pymupdf
import requests
import re
import pandas as pd
import asyncio
import threading
import os
import json
import re


class TransformRegistry:
    _registry: dict[str,Callable] = {}
    @classmethod
    def register(cls,transform_name:str,fn:Callable):
        cls._registry[transform_name] = fn
    
    @classmethod
    def get_registry(cls,transform_name:str):
        if transform_name not in cls._registry:
            raise ValueError(f"Transform name {transform_name} not found")
        return cls._registry.get(transform_name)

    @classmethod
    def apply_transform(cls,field:Any,transforms:list[dict],context:dict):
        for transform in transforms:
            transform_fn = cls.get_registry(transform.get('name',''))
            if transform_fn is None:
                raise ValueError(f"Transform name {transform.get('name')} not found")
            field = transform_fn(field,transform.get('args',{}),context)
        return field
    
def _split_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',"")
    parts = str(field).split(args['delimiter'])
    if args['index'] < len(parts):
        return parts[args['index']]
    return args.get('default',"")

def _replace_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',"")
    return str(field).replace(args['str_to_replace'],args['replace_with'])

def _strip_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',"")
    return str(field).strip()

def _recursive_file_glob(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    if args.get('recursive',False):
        return list(Path(field).rglob(args.get("files_pattern",'')))
    else:
        return list(Path(field).glob(args.get("files_pattern",'')))

def _absolute_filepath(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return Path(field).absolute()

def _file_name_property(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return Path(field).name

def _basename(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return Path(field).name

def _file_path_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return str(field)

def _startwith(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return str(field).startswith(args['prefix'])

def _regex_match(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return re.match(args['pattern'],str(field))

def _split_join(field:Any,args:dict,context:dict):
    part = []
    parts = str(field).split(args['delimiter'])
    if type(args["index"])==int:
        if args["index"]<len(parts):
            part = parts[args["index"]]
        else:
            part = args.get('default',[])
    elif type(args["index"])==list:
        part = [parts[i] for i in args["index"] if i<len(parts)]
    if field is None:
        return args.get('default',[])
    return args['join_with'].join(part)

def _page_number_offset(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    if args["file_start_page"] in context:
        file_start_page = context[args["file_start_page"]]
    elif args["file_start_page"] in field:
        file_start_page = field[args["file_start_page"]]
    else:
        file_start_page = 0
    return int(field) + int(file_start_page) - args['offset']

def _parent_folder_name(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return Path(field).parent.name

def _file_stem_op(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return Path(field).stem

def _join_list_to_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return args['delimiter'].join(field)    


def _enumerate_join_to_str(field:Any,args:dict,context:dict):
    if field is None:
        return args.get('default',[])
    return args['delimiter'].join([f"{i+1}. {item}" for i,item in enumerate(field)])


TransformRegistry.register("split_str",_split_str)
TransformRegistry.register("replace_str",_replace_str)
TransformRegistry.register("strip_str",_strip_str)
TransformRegistry.register("glob",_recursive_file_glob)
TransformRegistry.register("file_absolute_path",_absolute_filepath)
TransformRegistry.register("file_name_op",_file_name_property)
TransformRegistry.register("basename",_basename)
TransformRegistry.register("file_path_str",_file_path_str)
TransformRegistry.register("startswith",_startwith)
TransformRegistry.register("regex_match",_regex_match)    
TransformRegistry.register("split_join",_split_join)
TransformRegistry.register("page_number_offset",_page_number_offset)
TransformRegistry.register("parent_folder_name",_parent_folder_name)
TransformRegistry.register("file_stem_op",_file_stem_op)
TransformRegistry.register("join_list_to_str",_join_list_to_str)
TransformRegistry.register("enumerate_join_to_str",_enumerate_join_to_str)