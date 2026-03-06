"""
Math 扩展节点 - 支持三目运算和 round 函数
"""
import math


class MathTernary:
    """三目运算节点：condition ? value_if_true : value_if_false"""
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "condition": ("BOOLEAN", {"default": False}),
                "value_if_true": ("INT,FLOAT", {"default": 0}),
                "value_if_false": ("INT,FLOAT", {"default": 0}),
            }
        }
    
    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("result_int", "result_float")
    FUNCTION = "execute"
    CATEGORY = "utils/math"
    
    def execute(self, condition, value_if_true, value_if_false):
        result = value_if_true if condition else value_if_false
        # 判断输入类型，返回对应类型
        if isinstance(value_if_true, int) and isinstance(value_if_false, int):
            return (int(result), float(result))
        return (int(result), float(result))


class MathRound:
    """四舍五入节点 - 支持指定小数位数"""
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "value": ("INT,FLOAT", {"default": 0}),
                "decimal_places": ("INT", {"default": 0, "min": 0, "max": 10, "step": 1}),
            }
        }
    
    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("result_int", "result_float")
    FUNCTION = "execute"
    CATEGORY = "utils/math"
    
    def execute(self, value, decimal_place):
        multiplier = 10 ** decimal_place
        result_float = round(value * multiplier) / multiplier
        result_int = int(round(value))
        return (result_int, result_float)


