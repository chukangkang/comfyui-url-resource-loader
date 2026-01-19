# 遵循ComfyUI自定义节点标准导入规范
from .url_resource_loader import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# 暴露必要的变量（ComfyUI会自动扫描这些变量）
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# 可选：添加节点版本信息
__version__ = "1.0.0"
__author__ = "chukangkang"