import sys
import os

# 将当前目录加入Python路径（确保导入自定义节点）
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------
# 导入各URL加载节点类（需确保对应py文件存在）
# 兼容：包内相对导入 / 直接运行时绝对导入
# ---------------------------
try:
    from .LoadImageFromURL import LoadImageFromURL
    from .LoadVideoFromURL import LoadVideoFromURL
    from .LoadAudioFromURL import LoadAudioFromURL
    from .oss_uploader import OSS_Upload
except ImportError:
    from LoadImageFromURL import LoadImageFromURL
    from LoadVideoFromURL import LoadVideoFromURL
    from LoadAudioFromURL import LoadAudioFromURL
    from oss_uploader import OSS_Upload

# ---------------------------
# 统一节点映射（兼容传统ComfyUI格式）
# ---------------------------
NODE_CLASS_MAPPINGS = {
    "LoadImageFromURL": LoadImageFromURL,
    "LoadVideoFromURL": LoadVideoFromURL,
    "LoadAudioFromURL": LoadAudioFromURL,
    "OSS_Upload": OSS_Upload
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromURL": "🔌 Load Image From URL",
    "LoadVideoFromURL": "🔌 Load Video From URL",
    "LoadAudioFromURL": "🔌 Load Audio From URL",
    "OSS_Upload": "🔌 OSS Upload"
}

# ---------------------------
# 版本信息
# ---------------------------
__version__ = "1.1.0"
__author__ = "chukangkang"
__description__ = "URL资源加载器（支持图片/音频/视频）"

# 导出必要变量（ComfyUI标准要求）
__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS"
]