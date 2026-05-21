from __future__ import annotations
import re

class HelperFunctions:
    operations = {
        "contains":lambda x,y: y in x,
        "not_contains":lambda x,y: y not in x,
        "equals":lambda x,y: x == y,
        "not_equals":lambda x,y: x != y,
        "greater_than":lambda x,y: x > y,
        "less_than":lambda x,y: x < y,
        "greater_than_or_equal_to":lambda x,y: x >= y,
        "less_than_or_equal_to":lambda x,y: x <= y,
        "matches":lambda x,y: re.match(y,x),
        "not_matches":lambda x,y: not re.match(y,x),
        "startwith":lambda x,y: x.startswith(y),    
    }
    
    @classmethod
    def apply_operation(cls,record,field_cfg):
        try:
            if not field_cfg:
                return True
            field_name = field_cfg.get("field")
            field_op = field_cfg.get("ops")
            field_val = field_cfg.get("value")
            
            if field_name not in record:
                print(f"Field {field_name} not found in record")
                return False
                
            func = cls.operations.get(field_op)
            if func is None:
                raise ValueError(f"Operation {field_op} not found")
            
            record_val = str(record[field_name])
            choice_val = str(field_val)
            
            result = func(record_val, choice_val)
            #print(f"Applying operation: {field_name} ({record_val}) {field_op} {choice_val} -> {result}")
            return result
        except Exception as e:
            print(f"Error applying operation: {e}")
            return False
    
