# 文件名：LoadVideoFromURL.py
# 放置路径：ComfyUI/custom_nodes/LoadVideoFromURL.py

from __future__ import annotations
import os
import sys
import tempfile
import hashlib
import asyncio

# 将ComfyUI主目录添加到Python路径
comfy_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
if comfy_path not in sys.path:
    sys.path.insert(0, comfy_path)

# 导入ComfyUI核心模块
try:
    import folder_paths
    import aiohttp
except ImportError as e:
    print(f"[LoadVideoFromURL] Import error: {e}")
    print("[LoadVideoFromURL] Make sure this file is placed in ComfyUI/custom_nodes/ directory")
    raise

# ---------------------------
# 从URL加载视频的核心节点（传统格式，兼容ComfyUI v0.9.2+）
# ---------------------------
class LoadVideoFromURL:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_url": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
                "save_to_input_folder": ("BOOLEAN", {
                    "default": False,
                    "label_on": "save",
                    "label_off": "temp"
                }),
                "filename": ("STRING", {
                    "default": "downloaded_video",
                    "multiline": False
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "load_video"
    CATEGORY = "loaders"
    OUTPUT_NODE = False

    def load_video(self, video_url: str, save_to_input_folder: bool, filename: str):
        """同步包装异步加载逻辑"""
        try:
            # 获取或创建事件循环
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 运行异步函数
            video_path = loop.run_until_complete(
                self._load_video_async(video_url, save_to_input_folder, filename)
            )
            return (video_path,)
        except Exception as e:
            raise RuntimeError(f"[LoadVideoFromURL] Failed to load video: {str(e)}")
    
    async def _load_video_async(self, video_url: str, save_to_input_folder: bool, filename: str) -> str:
        """异步加载视频核心逻辑（保留原算法不变）"""
        # 基础输入验证
        if not video_url:
            raise ValueError("Error: Video URL cannot be empty!")
        
        if not video_url.startswith(('http://', 'https://')):
            raise ValueError(f"Error: Invalid URL format! Must start with http:// or https:// (got: {video_url})")
        
        temp_file = None
        video_path = ""
        
        try:
            # 1. 创建HTTP会话并下载视频
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
                
                return video_path
                
        except Exception as e:
            # 异常处理：清理临时文件
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            raise RuntimeError(f"[LoadVideoFromURL] Failed to load video: {str(e)}")
    
    @classmethod
    def IS_CHANGED(cls, video_url: str, save_to_input_folder: bool, filename: str):
        """生成缓存指纹（ComfyUI缓存机制）"""
        fingerprint_data = f"{video_url}|{save_to_input_folder}|{filename}".encode('utf-8')
        return hashlib.md5(fingerprint_data).hexdigest()