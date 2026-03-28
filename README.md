# AutoNCM2SP

一个基于 Python 的网易云音乐歌单自动下载工具，支持增量更新、音质自动降级与账号登录。

## 功能特性

- **歌单下载**：通过歌单链接自动获取全部歌曲并下载到本地
- **增量更新**：记录已下载歌曲，每次运行只下载新增内容
- **音质优先级**：默认 Hi-Res，不支持时自动向下兼容（Hi-Res → 无损 → 极高 → 较高 → 标准）
- **账号登录**：支持手机号 / 邮箱登录，登录后可获取完整歌曲（未登录仅提供30秒试听片段）
- **一键启动**：`start.bat` 自动创建虚拟环境、安装依赖、运行程序

## 环境要求

- Python 3.8 或更高版本
- Windows（`start.bat` 为 Windows 批处理脚本）

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/Trantormann/AutoNCM2SP.git
cd AutoNCM2SP
```

### 2. 配置

复制配置模板并编辑：

```bash
copy config\config.example.json config\config.json
```

编辑 `config/config.json`：

```json
{
    "playlist_url": "https://music.163.com/playlist?id=歌单ID",
    "download_dir": "./downloads",
    "default_quality": "hires",
    "login": {
        "phone": "手机号",
        "email": "",
        "password": "密码"
    }
}
```

| 字段 | 说明 |
|------|------|
| `playlist_url` | 网易云歌单链接，支持 `?id=xxx` 格式或直接填写歌单 ID |
| `download_dir` | 下载目录，支持相对路径和绝对路径 |
| `default_quality` | 优先音质：`hires` / `lossless` / `exhigh` / `higher` / `standard` |
| `login.phone` | 手机号（与 `email` 二选一） |
| `login.email` | 邮箱（与 `phone` 二选一） |
| `login.password` | 明文密码 |

> **注意**：`config.json` 已被 `.gitignore` 排除，不会上传到仓库，账号信息不会泄露。

### 3. 启动

双击 `start.bat`，脚本将自动完成以下步骤：

1. 检测 Python 环境
2. 创建并激活虚拟环境（首次运行时询问是否创建）
3. 安装 / 更新依赖
4. 启动主程序

## 项目结构

```
AutoNCM2SP/
├── config/
│   ├── config.json           # 本地配置（不纳入版本控制）
│   ├── config.example.json   # 配置模板
│   └── settings.py           # 配置管理模块
├── core/
│   ├── ncm_api.py            # 网易云 API 封装（基于 pyncm）
│   ├── downloader.py         # 歌曲下载器
│   └── playlist.py           # 歌单管理与增量逻辑
├── database/
│   ├── db.py                 # SQLite 数据库操作
│   └── models.py             # 数据模型
├── downloads/                # 歌曲下载目录（自动创建）
├── main.py                   # 程序入口
├── requirements.txt          # 依赖列表
└── start.bat                 # Windows 一键启动脚本
```

## 依赖

| 包 | 用途 |
|----|------|
| [pyncm](https://github.com/mos9527/pyncm) | 网易云音乐 API |
| [requests](https://docs.python-requests.org/) | HTTP 下载 |

## 常见问题

**Q：下载的歌曲只有几十秒？**  
A：未登录时网易云只提供试听片段。请在 `config/config.json` 的 `login` 字段中填写账号信息。

**Q：Hi-Res 下载失败？**  
A：Hi-Res 需要网易云黑胶 VIP。程序会自动降级到下一可用音质。

**Q：如何只下载特定音质？**  
A：修改 `config.json` 中的 `default_quality` 字段。

## 许可证

[MIT](LICENSE)
