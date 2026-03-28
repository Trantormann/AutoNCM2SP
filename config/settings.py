"""
配置管理模块
处理配置文件的读取、写入和默认值管理
"""

import json
import os
from pathlib import Path


# 默认配置
DEFAULT_CONFIG = {
    "playlists": [                 # 歌单列表（支持多歌单-多目录映射）
        {
            "name": "默认歌单",    # 歌单名称（用于显示）
            "url": "",             # 歌单链接
            "download_dir": "./downloads",  # 该歌单的下载目录
            "quality": "hires"     # 该歌单的音质（可选，默认使用 default_quality）
        }
    ],
    "default_quality": "hires",    # 默认音质: hires/lossless/exhigh/higher/standard
    "login": {
        "phone": "",     # 手机号（与 email 二选一）
        "email": "",     # 邮箱（与 phone 二选一）
        "password": ""   # 密码（明文）
    },
    # 兼容旧配置（已弃用，但保留读取支持）
    "playlist_url": "",
    "download_dir": "./downloads"
}

# 音质优先级（从高到低）
QUALITY_ORDER = ['hires', 'lossless', 'exhigh', 'higher', 'standard']

# 音质显示名称映射
QUALITY_MAPPING = {
    'hires': 'Hi-Res',
    'lossless': '无损',
    'exhigh': '极高',
    'higher': '较高',
    'standard': '标准'
}


class Settings:
    """配置管理类"""
    
    def __init__(self, config_path=None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 config/config.json
        """
        if config_path is None:
            # 获取当前文件所在目录的父目录（项目根目录）
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "config.json"
        
        self.config_path = Path(config_path)
        self.config = {}
        self.load()
    
    def load(self):
        """加载配置文件，如果不存在则创建默认配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和用户配置（处理新增配置项）
                    self.config = {**DEFAULT_CONFIG, **loaded_config}
            except (json.JSONDecodeError, IOError) as e:
                print(f"配置文件读取失败: {e}，使用默认配置")
                self.config = DEFAULT_CONFIG.copy()
                self.save()
        else:
            print("配置文件不存在，创建默认配置")
            self.config = DEFAULT_CONFIG.copy()
            self.save()
    
    def save(self):
        """保存配置到文件"""
        try:
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"配置文件保存失败: {e}")
    
    def get(self, key, default=None):
        """
        获取配置项
        
        Args:
            key: 配置项键名
            default: 默认值
        
        Returns:
            配置项值
        """
        return self.config.get(key, default)
    
    def set(self, key, value):
        """
        设置配置项
        
        Args:
            key: 配置项键名
            value: 配置项值
        """
        self.config[key] = value
        self.save()
    
    def get_download_dir(self):
        """获取下载目录的绝对路径"""
        download_dir = self.get('download_dir', './downloads')
        # 如果是相对路径，转换为绝对路径
        path = Path(download_dir)
        if not path.is_absolute():
            # 相对于项目根目录
            base_dir = Path(__file__).parent.parent
            path = base_dir / path
        return str(path.resolve())
    
    def get_login_config(self) -> dict:
        """获取登录配置，合并默认空值"""
        default = {"phone": "", "email": "", "password": ""}
        user = self.get('login', {})
        if isinstance(user, dict):
            default.update(user)
        return default

    def get_playlists(self) -> list:
        """
        获取歌单列表，兼容新旧配置格式
        
        Returns:
            歌单配置列表
        """
        playlists = self.get('playlists', [])
        if playlists and isinstance(playlists, list) and len(playlists) > 0:
            # 新格式：playlists 数组
            valid_playlists = []
            for pl in playlists:
                if isinstance(pl, dict) and pl.get('url'):
                    valid_playlists.append(pl)
            if valid_playlists:
                return valid_playlists
        
        # 旧格式兼容：使用 playlist_url 和 download_dir
        old_url = self.get('playlist_url', '')
        if old_url:
            return [{
                'name': '默认歌单',
                'url': old_url,
                'download_dir': self.get('download_dir', './downloads'),
                'quality': self.get('default_quality', 'hires')
            }]
        
        return []
    
    def validate(self):
        """
        验证配置是否有效
        
        Returns:
            (is_valid, error_message)
        """
        # 检查歌单配置
        playlists = self.get_playlists()
        if not playlists:
            return False, "请配置歌单链接 (在 playlists 数组中添加 url)"
        
        # 检查音质设置
        quality = self.get('default_quality', 'hires')
        if quality not in QUALITY_ORDER:
            return False, f"无效的音质设置: {quality}，可选值: {', '.join(QUALITY_ORDER)}"
        
        return True, ""


# 全局配置实例
_settings = None


def get_settings():
    """获取全局配置实例（单例模式）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
