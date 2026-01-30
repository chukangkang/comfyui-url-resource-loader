# 文件名：LoadVideoFromURL.py
# 放置路径：ComfyUI/custom_nodes/LoadVideoFromURL.py

from __future__ import annotations
import os
import sys
import tempfile
import hashlib

# 将ComfyUI主目录添加到Python路径
comfy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if comfy_path not in sys.path:
    sys.path.insert(0, comfy_path)

# 导入ComfyUI核心模块
try:
    from typing import Optional
    from typing_extensions import override
    import folder_paths
    from comfy_api.latest import ComfyExtension, io, Input, InputImpl, Types
    import aiohttp
except ImportError as e:
    print(f"[LoadVideoFromURL] Import error: {e}")
    print("[LoadVideoFromURL] Make sure this file is placed in ComfyUI/custom_nodes/ directory")
    raise

# ---------------------------
# 从URL加载视频的核心节点（修复异步循环问题）
# ---------------------------
class ComfyVideoURLLoader(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="ComfyVideoURLLoader",
            display_name="Load Video From URL",
            category="image/video",
            description="Load a video from a remote URL (supports http/https)",
            inputs=[
                io.String.Input(
                    "video_url", 
                    default="", 
                    tooltip="URL of the video to load (e.g., https://example.com/video.mp4)\nSupported formats: mp4, webm, mov, avi, mkv, flv"
                ),
                io.Boolean.Input(
                    "save_to_input_folder", 
                    default=False, 
                    tooltip="Whether to save the downloaded video to ComfyUI input folder\nIf False, video will be saved as temporary file"
                ),
                io.String.Input(
                    "filename", 
                    default="downloaded_video", 
                    tooltip="Filename for saved video (without extension)"
                ),
            ],
            outputs=[
                io.Video.Output(),
            ],
        )
    
    # 关键修改：直接使用异步execute方法，而非同步包装
    @classmethod
    async def execute(cls, video_url: str, save_to_input_folder: bool, filename: str) -> io.NodeOutput:
        """异步执行核心逻辑（直接兼容ComfyUI的异步执行环境）"""
        # 基础输入验证
        if not video_url:
            raise ValueError("Error: Video URL cannot be empty!")
        
        if not video_url.startswith(('http://', 'https://')):
            raise ValueError(f"Error: Invalid URL format! Must start with http:// or https:// (got: {video_url})")
        
        temp_file = None
        video_path = ""
        
        try:
            # 1. 创建HTTP会话并下载视频（使用ComfyUI的事件循环）
            timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(video_url) as response:
                    # 检查HTTP响应状态
                    response.raise_for_status()
                    print(f"[LoadVideoFromURL] Successfully connected to {video_url}")
                    
                    # 2. 自动识别文件扩展名
                    file_ext = '.mp4'  # 默认扩展名
                    if '.' in video_url:
                        url_ext = video_url.split('.')[-1].split('?')[0].lower()
                        supported_exts = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'mpeg', 'mpg', 'wmv']
                        if url_ext in supported_exts:
                            file_ext = f'.{url_ext}'
                    
                    # 3. 确定保存路径
                    if save_to_input_folder:
                        # 保存到ComfyUI输入文件夹（永久保存）
                        input_dir = folder_paths.get_input_directory()
                        os.makedirs(input_dir, exist_ok=True)
                        video_path = os.path.join(input_dir, f"{filename}{file_ext}")
                        
                        # 避免文件名重复
                        counter = 1
                        while os.path.exists(video_path):
                            video_path = os.path.join(input_dir, f"{filename}_{counter}{file_ext}")
                            counter += 1
                        
                        # 分块下载（适合大文件）
                        with open(video_path, 'wb') as f:
                            downloaded_size = 0
                            while True:
                                chunk = await response.content.read(8192)  # 8KB分块
                                if not chunk:
                                    break
                                f.write(chunk)
                                downloaded_size += len(chunk)
                        
                        print(f"[LoadVideoFromURL] Video saved to: {video_path} ({downloaded_size/1024/1024:.2f} MB)")
                    else:
                        # 创建临时文件（会话结束后自动清理）
                        temp_file = tempfile.NamedTemporaryFile(
                            suffix=file_ext, 
                            delete=False,
                            mode='wb'
                        )
                        
                        # 下载到临时文件
                        with temp_file:
                            downloaded_size = 0
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                temp_file.write(chunk)
                                downloaded_size += len(chunk)
                        
                        video_path = temp_file.name
                        print(f"[LoadVideoFromURL] Video downloaded to temporary file: {video_path} ({downloaded_size/1024/1024:.2f} MB)")
                
                # 4. 创建Video对象并返回（与原生节点完全兼容）
                video_object = InputImpl.VideoFromFile(video_path)
                return io.NodeOutput(video_object)
                
        except Exception as e:
            # 异常处理：清理临时文件
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            raise RuntimeError(f"[LoadVideoFromURL] Failed to load video: {str(e)}")
    
    @classmethod
    def fingerprint_inputs(cls, video_url: str, save_to_input_folder: bool, filename: str):
        """生成缓存指纹（ComfyUI缓存机制）"""
        fingerprint_data = f"{video_url}|{save_to_input_folder}|{filename}".encode('utf-8')
        return hashlib.md5(fingerprint_data).hexdigest()
    
    @classmethod
    def validate_inputs(cls, video_url: str, save_to_input_folder: bool, filename: str):
        """输入验证（ComfyUI节点系统要求）"""
        if not video_url:
            return "Error: Video URL cannot be empty!"
        
        if not video_url.startswith(('http://', 'https://')):
            return "Error: URL must start with http:// or https://!"
        
        if save_to_input_folder and filename:
            invalid_chars = r'\/:*?"<>|'
            if any(c in filename for c in invalid_chars):
                return f"Error: Filename cannot contain these characters: {invalid_chars}!"
        
        return True


# ---------------------------
# 兼容ComfyUI旧版节点映射（确保节点能被识别）
# ---------------------------
NODE_CLASS_MAPPINGS = {
    "ComfyVideoURLLoader": ComfyVideoURLLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyVideoURLLoader": "🎥 Load Video From URL"
}
