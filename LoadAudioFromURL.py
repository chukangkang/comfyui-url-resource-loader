import io as std_io  # 重命名标准库io，避免冲突
import torch
import requests
import torchaudio
from typing_extensions import override
from comfy_api.latest import ComfyExtension, io as ComfyIO  # ComfyUI的io模块
import comfy.model_management

# 仅支持URL加载的音频节点（修复命名冲突+适配阿里云OSS）
class LoadAudioFromURL(ComfyIO.ComfyNode):
    @classmethod
    def define_schema(cls) -> ComfyIO.Schema:
        return ComfyIO.Schema(
            node_id="LoadAudioFromURL",
            category="loaders",
            inputs=[
                ComfyIO.String.Input(
                    "audio_url",
                    default="",
                    tooltip="音频文件的URL地址（支持MP3/WAV/FLAC等主流格式，输出将适配16000Hz采样率）"
                ),
            ],
            outputs=[ComfyIO.Audio.Output()],
        )

    @classmethod
    def execute(cls, audio_url) -> ComfyIO.NodeOutput:
        # 校验URL非空
        if not audio_url or not audio_url.strip():
            raise ValueError("音频URL不能为空，请填写有效的音频文件地址")
        
        # 核心逻辑：从URL加载音频并标准化
        waveform, sample_rate = cls._load_audio_from_url(audio_url.strip())
        
        # 适配代码库中音频编码器的采样率（统一转为16000Hz）
        target_sample_rate = 16000
        if sample_rate != target_sample_rate:
            waveform = torchaudio.functional.resample(
                waveform,
                orig_freq=sample_rate,
                new_freq=target_sample_rate,
                resampling_method="sinc_interpolation"
            )
            sample_rate = target_sample_rate

        # 标准化输出格式 [B, C, T]（兼容AudioInput类型定义）
        if len(waveform.shape) == 1:
            waveform = waveform.unsqueeze(0).unsqueeze(0)  # [T] -> [1,1,T]
        elif len(waveform.shape) == 2:
            waveform = waveform.unsqueeze(0)  # [C,T] -> [1,C,T]
        
        # 移至合适的设备（兼容ComfyUI模型管理逻辑）
        waveform = waveform.to(comfy.model_management.intermediate_device())

        # 输出格式严格匹配AudioInput TypedDict
        audio_output = {
            "waveform": waveform,
            "sample_rate": sample_rate
        }
        return ComfyIO.NodeOutput(audio_output)

    @staticmethod
    def _load_audio_from_url(url: str) -> tuple[torch.Tensor, int]:
        """从URL加载音频的核心方法，适配阿里云OSS等存储服务"""
        try:
            # 构建适配阿里云OSS的请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "audio/mpeg,audio/wav,audio/flac,audio/ogg;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",  # 禁用压缩，避免二进制数据损坏
                "Range": "bytes=0-"  # 支持分块下载，适配大文件
            }
            # 发送HTTP请求获取音频二进制数据（增加超时重试）
            max_retries = 2
            for retry in range(max_retries + 1):
                try:
                    response = requests.get(
                        url,
                        stream=True,
                        timeout=60,  # 延长超时时间（适配阿里云OSS）
                        headers=headers,
                        verify=False,  # 忽略SSL校验（阿里云OSS无需校验）
                        allow_redirects=True  # 允许重定向
                    )
                    response.raise_for_status()
                    break  # 成功则退出重试
                except requests.exceptions.RequestException as e:
                    if retry == max_retries:
                        raise e
                    import time
                    time.sleep(1)  # 重试前等待1秒

            # 读取二进制数据（使用标准库io，避免命名冲突）
            audio_bytes = std_io.BytesIO(response.content)
            audio_bytes.seek(0)  # 重置文件指针到开头
            
            # 加载音频（指定格式，适配WAV文件）
            waveform, sample_rate = torchaudio.load(
                audio_bytes,
                format="wav" if url.lower().endswith(".wav") else None
            )
            
            return waveform, sample_rate
        
        except requests.exceptions.Timeout:
            raise RuntimeError(f"加载音频超时：URL={url}（超时时间60秒）")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"URL返回错误状态码：{e.response.status_code}，URL={url}")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"无法连接到音频服务器：URL={url}")
        except Exception as e:
            # 通用异常捕获，输出详细错误信息
            error_detail = str(e)
            if "metadata" in error_detail.lower() or "audio" in error_detail.lower():
                raise RuntimeError(f"URL不是有效的音频文件：{url}，错误信息：{error_detail}")
            elif "BytesIO" in error_detail:
                raise RuntimeError(f"音频数据读取失败（命名冲突）：{url}，错误信息：{error_detail}")
            else:
                raise RuntimeError(f"从URL加载音频失败：{error_detail}，URL={url}")

# 兼容ComfyUI旧版节点映射（确保节点能被识别）
NODE_CLASS_MAPPINGS = {
    "LoadAudioFromURL": LoadAudioFromURL
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadAudioFromURL": "Load Audio From URL"
}
