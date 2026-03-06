"""
Math 扩展节点 - 三目运算
"""


class MathTernary:
    """三目运算节点：condition ? a : b"""
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "a": ("INT,FLOAT", {"default": 0}),
                "b": ("INT,FLOAT", {"default": 0}),
                "condition": ("STRING", {"default": "a > b ? a : b", "multiline": False}),
            }
        }
    
    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("result_int", "result_float")
    FUNCTION = "execute"
    CATEGORY = "utils/math"
    
    def execute(self, a, b, condition):
        try:
            # 支持三目运算符格式: condition ? value_if_true : value_if_false
            # 例如: a > b ? 1080 : round(1080*a/b)
            import re
            
            # 匹配三目运算符 pattern
            match = re.match(r'^(.+?)\s*\?\s*(.+?)\s*:\s*(.+)$', condition.strip())
            
            # 提供内置函数给 eval 使用
            eval_globals = {
                "a": a,
                "b": b,
                "round": round,
                "abs": abs,
                "min": min,
                "max": max,
                "pow": pow,
            }
            
            if match:
                # 解析三目运算符
                cond_expr = match.group(1).strip()
                true_expr = match.group(2).strip()
                false_expr = match.group(3).strip()
                
                # 计算条件结果
                cond_result = eval(cond_expr, {"__builtins__": {}}, eval_globals)
                
                if cond_result:
                    result = eval(true_expr, {"__builtins__": {}}, eval_globals)
                else:
                    result = eval(false_expr, {"__builtins__": {}}, eval_globals)
            else:
                # 普通条件表达式
                cond_result = eval(condition, {"__builtins__": {}}, eval_globals)
                result = a if cond_result else b
            
            return (int(result), float(result))
        except Exception as e:
            raise ValueError(f"Condition evaluation error: {str(e)}")
