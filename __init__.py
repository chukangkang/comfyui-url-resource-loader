from typing_extensions import override
from comfy_api.latest import ComfyExtension, io
import sys
import os

# 将当前目录加入Python路径（确保导入自定义节点）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------
# 导入各URL加载节点类（需确保对应py文件存在）
# ---------------------------
# 图片URL加载节点（LoadImageFromURL）
from .LoadImageFromURL import LoadImageFromURL
# 视频URL加载节点（LoadVideoFromURL）
from .LoadVideoFromURL import LoadVideoFromURL  # 需确保该文件存在
# 音频URL加载节点（LoadAudioFromURL）
from .LoadAudioFromURL import LoadAudioFromURL  # 需确保该文件存在
# OSS上传节点（OSS_Upload）
from .oss_uploader import OSS_Upload

# ---------------------------
# 传统节点映射（兼容旧版ComfyUI）
# ---------------------------
NODE_CLASS_MAPPINGS = {
    "LoadImageFromURL": LoadImageFromURL,
    "LoadVideoFromURL": LoadVideoFromURL,
    "LoadAudioFromURL": LoadAudioFromURL,
    "OSS_Upload": OSS_Upload
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromURL": "Load Image From URL",
    "LoadVideoFromURL": "Load Video From URL",
    "LoadAudioFromURL": "Load Audio From URL",
    "OSS_Upload": "Upload to OSS"
}

# ---------------------------
# 统一扩展注册类（整合所有URL加载节点）
# ---------------------------
class URLLoaderExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        # 汇总所有URL加载节点
        return [
            LoadImageFromURL,
            LoadVideoFromURL,
            LoadAudioFromURL,
            OSS_Upload
        ]

# ---------------------------
# ComfyUI扩展标准入口函数（唯一入口）
# ---------------------------
async def comfy_entrypoint() -> URLLoaderExtension:
    print("[URLLoaderExtension] Image/Video/Audio URL Loader loaded successfully!")
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
__version__ = "1.1.0"  # 升级版本号，标识新增了VHS视频加载功能
__author__ = "chukangkang"
__description__ = "URL资源加载器（支持图片/音频/视频）"