#!/usr/bin/env python3
"""
网易云歌单下载工具 - 主程序
"""

import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings
from database.db import get_database
from utils.logger import get_logger

log = get_logger()


def print_banner():
    """打印程序横幅"""
    log.info("=" * 60)
    log.info("       网易云歌单下载工具")
    log.info("=" * 60)


def check_api():
    """检查 pyncm 库是否可用"""
    import sys
    log.info("正在检查 API 库...")
    log.info("  当前 Python: %s", sys.executable)

    try:
        import pyncm
        log.info("✓ pyncm 已加载")
        return True
    except ImportError as e:
        log.error("✗ pyncm 未安装: %s", e)
    except Exception as e:
        log.error("✗ pyncm 加载失败 (%s): %s", type(e).__name__, e)

    log.info("请在当前 Python 环境中安装依赖:")
    log.info("  %s -m pip install pyncm", sys.executable)
    return False


def check_config():
    """检查配置是否有效"""
    settings = get_settings()
    is_valid, error_msg = settings.validate()
    
    if not is_valid:
        print(f"配置错误: {error_msg}")
        print()
        print("请编辑 config/config.json 配置文件:")
        print('  {')
        print('      "playlist_url": "https://music.163.com/playlist?id=xxx",')
        print('      "download_dir": "./downloads",')
        print('      "default_quality": "hires",')
        print('      "api_server_url": "http://localhost:3000"')
        print('  }')
        print()
        return False
    
    print("配置检查通过")
    print(f"  歌单链接: {settings.get('playlist_url')}")
    print(f"  下载目录: {settings.get_download_dir()}")
    print(f"  默认音质: {QUALITY_MAPPING.get(settings.get('default_quality'), '未知')}")
    login_cfg = settings.get_login_config()
    account = login_cfg.get('phone') or login_cfg.get('email') or ''
    if account:
        print(f"  登录账号: {account}")
    else:
        print("  登录账号: 未配置（游客模式，只能下载试听片段）")
        print("  → 请在 config/config.json 中配置 login.phone / login.email 和 login.password")
    print()
    return True


def show_stats():
    """显示下载统计"""
    db = get_database()
    count = db.get_download_count()
    log.info("已下载歌曲总数: %d 首", count)


def clear_records(auto_mode: bool = False):
    """清除所有下载记录"""
    db = get_database()
    count = db.get_download_count()
    log.info("当前下载记录: %d 首", count)
    
    confirm = 'yes' if auto_mode else input("确定要清除所有下载记录吗? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if db.clear_all_records():
            log.info("✓ 下载记录已清除")
        else:
            log.error("✗ 清除失败")
    else:
        log.info("已取消")


def process_single_playlist(playlist_url: str, download_dir: str, default_quality: str, auto_mode: bool = False):
    """处理单个歌单下载"""
    from pathlib import Path
    from core.playlist import PlaylistManager
    
    # 创建独立的歌单管理器
    manager = PlaylistManager()
    manager.download_dir = Path(download_dir)
    manager.download_dir.mkdir(parents=True, exist_ok=True)
    
    success, msg = manager.load_playlist_from_url(playlist_url)
    
    if not success:
        log.error("错误: %s", msg)
        return False

    manager.show_playlist_info()
    
    if not manager.new_songs:
        log.info("所有歌曲已是最新，无需下载")
        return True

    confirm = '' if auto_mode else input(f"是否开始下载 {len(manager.new_songs)} 首新歌曲? (Y/n): ").strip().lower()
    
    if confirm and confirm not in ('y', 'yes', ''):
        log.info("已取消下载")
        return True

    manager.download_all(target_quality=default_quality)
    return True


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='网易云歌单下载工具')
    parser.add_argument('--clear', action='store_true', help='清除所有下载记录')
    parser.add_argument('--auto', action='store_true', help='自动模式（非交互，适合定时任务）')
    args = parser.parse_args()
    
    print_banner()
    
    # 检查 API 库
    if not check_api():
        if not args.auto:
            input("按回车键退出...")
        return 1
    
    # 处理清除记录命令
    if args.clear:
        clear_records(auto_mode=args.auto)
        if not args.auto:
            input("按回车键退出...")
        return 0
    
    # 检查配置
    settings = get_settings()
    is_valid, error_msg = settings.validate()
    
    if not is_valid:
        log.error("配置错误: %s", error_msg)
        log.info("请编辑 config/config.json 配置文件")
        if not args.auto:
            input("按回车键退出...")
        return 1
    
    # 显示配置信息
    log.info("配置检查通过")
    playlists = settings.get_playlists()
    log.info("  歌单数量: %d 个", len(playlists))
    login_cfg = settings.get_login_config()
    account = login_cfg.get('phone') or login_cfg.get('email') or ''
    if account:
        log.info("  登录账号: %s", account)
    else:
        log.warning("  登录账号: 未配置（游客模式）")
    
    show_stats()
    
    # 处理所有歌单
    default_quality = settings.get('default_quality', 'hires')
    
    for i, pl in enumerate(playlists, 1):
        log.info("%s", '=' * 60)
        log.info("处理歌单 %d/%d: %s", i, len(playlists), pl.get('name', '未命名'))
        log.info("下载目录: %s", pl.get('download_dir', './downloads'))
        log.info("%s", '=' * 60)
        
        process_single_playlist(
            pl['url'],
            pl.get('download_dir', './downloads'),
            pl.get('quality', default_quality),
            auto_mode=args.auto
        )

    log.info("%s", '=' * 60)
    log.info("所有歌单处理完毕")
    log.info("%s", '=' * 60)
    
    if not args.auto:
        input("按回车键退出...")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("用户取消操作")
        sys.exit(1)
    except Exception as e:
        log.exception("程序异常: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)
