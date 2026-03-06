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
                "condition": ("STRING", {"default": "a > b", "multiline": False}),
            }
        }
    
    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("result_int", "result_float")
    FUNCTION = "execute"
    CATEGORY = "utils/math"
    
    def execute(self, a, b, condition):
        try:
            # 计算条件表达式，返回 True 或 False
            cond_result = eval(condition, {"__builtins__": {}, "a": a, "b": b})
            result = a if cond_result else b
            return (int(result), float(result))
        except Exception as e:
            raise ValueError(f"Condition evaluation error: {str(e)}")



