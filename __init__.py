import sys
import os

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

# 将当前目录加入Python路径（确保导入自定义节点）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------
# 导入各URL加载节点类（需确保对应py文件存在）
# ---------------------------
# 图片URL加载节点（LoadImageFromURL）
from .LoadImageFromURL import LoadImageFromURL
# 视频URL加载节点（LoadVideoFromURL）
from .LoadVideoFromURL import ComfyVideoURLLoader
# 音频URL加载节点（LoadAudioFromURL）
from .LoadAudioFromURL import LoadAudioFromURL
# 内存清理节点（ClearMemoryDeep）
from .ClearMemoryDeep import ClearMemoryDeepNode

# ---------------------------
# 传统节点映射（兼容旧版ComfyUI）
# ---------------------------
NODE_CLASS_MAPPINGS = {
    "LoadImageFromURL": LoadImageFromURL,
    "ComfyVideoURLLoader": ComfyVideoURLLoader,
    "LoadAudioFromURL": LoadAudioFromURL,
    "ClearMemoryDeepEnd": ClearMemoryDeepNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromURL": "🔌 Load Image From URL",
    "ComfyVideoURLLoader": "🔌 Load Video From URL",
    "LoadAudioFromURL": "🔌 Load Audio From URL",
    "ClearMemoryDeepEnd": "🚀 深度内存清洗（容器优化）"
}

# ---------------------------
# 统一扩展注册类（整合所有URL加载节点）
# ---------------------------
class URLLoaderExtension(ComfyExtension):
    @override
    async def get_nodes(self):
        return [
            LoadImageFromURL,
            ComfyVideoURLLoader,
            LoadAudioFromURL,
            ClearMemoryDeepNode
        ]

# ---------------------------
# ComfyUI扩展标准入口函数（唯一入口）
# ---------------------------
async def comfy_entrypoint() -> URLLoaderExtension:
    print("[URLLoaderExtension] Image/Video/Audio URL Loader + Memory Cleaner loaded successfully!")
    return URLLoaderExtension()

# ---------------------------
# 导出必要变量（ComfyUI标准要求）
# ---------------------------
__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "comfy_entrypoint"
]

# 可选：添加节点版本信息
__version__ = "1.4.0"
__author__ = "chukangkang"
__description__ = "URL资源加载器（支持图片/音频/视频） + 深度内存清理"