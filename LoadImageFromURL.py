import requests
import torch
import numpy as np
from PIL import Image, ImageOps
import folder_paths
from io import BytesIO

class LoadImageFromURL:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image_url": ("STRING", {"default": "https://example.com/image.jpg", "multiline": False}),
                "width": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
                "height": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"
    CATEGORY = "image/loaders"

    def load_image(self, image_url, width, height):
        # 从URL下载图片
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()  # 抛出HTTP错误
            img = Image.open(BytesIO(response.content)).convert("RGB")
        except Exception as e:
            raise Exception(f"Failed to load image from URL: {str(e)}")
        
        # 处理尺寸（保留原生逻辑，0表示使用原图尺寸）
        if width > 0 and height > 0:
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        elif width > 0:
            ratio = width / img.width
            height = int(img.height * ratio)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        elif height > 0:
            ratio = height / img.height
            width = int(img.width * ratio)
            img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        # 转换为ComfyUI标准张量格式
        img = ImageOps.exif_transpose(img)
        img_np = np.array(img).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_np)[None,]
        
        # 创建空mask（原生接口兼容）
        mask = torch.ones((1, img_tensor.shape[1], img_tensor.shape[2]), dtype=torch.float32)
        
        return (img_tensor, mask)

# 节点映射（ComfyUI标准）
NODE_CLASS_MAPPINGS = {
    "LoadImageFromURL": LoadImageFromURL
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageFromURL": "🔌 Load Image From URL"
}

