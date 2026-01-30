import io as std_io  # 重命名标准库io，避免冲突
import torch
import requests
import torchaudio

# 仅支持URL加载的音频节点（传统格式，兼容ComfyUI v0.9.2+）
class LoadAudioFromURL:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio_url": ("STRING", {
                    "default": "",
                    "multiline": False
                }),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("audio",)
    FUNCTION = "load_audio"
    CATEGORY = "loaders"
    OUTPUT_NODE = False

    def load_audio(self, audio_url):
        """加载音频核心逻辑（保留原算法不变）"""
        # 校验URL非空
        if not audio_url or not audio_url.strip():
            raise ValueError("音频URL不能为空，请填写有效的音频文件地址")
        
        # 从URL加载音频并标准化
        waveform, sample_rate = self._load_audio_from_url(audio_url.strip())
        
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

        # 标准化输出格式 [C, T]（ComfyUI音频标准）
        if len(waveform.shape) == 1:
            waveform = waveform.unsqueeze(0)  # [T] -> [1,T]
        elif len(waveform.shape) == 3:
            waveform = waveform.squeeze(0)  # [B,C,T] -> [C,T]

        # 输出格式匹配ComfyUI音频类型
        audio_output = {
            "waveform": waveform,
            "sample_rate": sample_rate
        }
        return (audio_output,)

    @staticmethod
    def _load_audio_from_url(url: str) -> tuple:
        """从URL加载音频的核心方法，保留原算法不变"""
        try:
            # 构建请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "audio/mpeg,audio/wav,audio/flac,audio/ogg;q=0.9,*/*;q=0.8",
                "Accept-Encoding": "identity",
                "Range": "bytes=0-"
            }
            
            # 发送HTTP请求获取音频二进制数据（增加超时重试）
            max_retries = 2
            for retry in range(max_retries + 1):
                try:
                    response = requests.get(
                        url,
                        stream=True,
                        timeout=60,
                        headers=headers,
                        verify=False,
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if retry == max_retries:
                        raise e
                    import time
                    time.sleep(1)

            # 读取二进制数据
            audio_bytes = std_io.BytesIO(response.content)
            audio_bytes.seek(0)
            
            # 加载音频
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
            error_detail = str(e)
            if "metadata" in error_detail.lower() or "audio" in error_detail.lower():
                raise RuntimeError(f"URL不是有效的音频文件：{url}，错误信息：{error_detail}")
            elif "BytesIO" in error_detail:
                raise RuntimeError(f"音频数据读取失败（命名冲突）：{url}，错误信息：{error_detail}")
            else:
                raise RuntimeError(f"从URL加载音频失败：{error_detail}，URL={url}")

# 兼容ComfyUI旧版节点映射
NODE_CLASS_MAPPINGS = {
    "LoadAudioFromURL": LoadAudioFromURL
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadAudioFromURL": "🔌 Load Audio From URL"
}
