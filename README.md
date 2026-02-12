# DXGI 屏幕捕获 + 超低带宽远程桌面

基于 DXGI Desktop Duplication API 的高性能屏幕捕获库和远程桌面系统。

## 📦 项目组成

### 1️⃣ DXGI 屏幕捕获 DLL

高性能 Windows 屏幕捕获库，支持全屏捕获和脏矩形增量捕获。

**核心功能**：
- ✅ 全屏捕获（BGRA格式）
- ✅ 脏矩形检测（实时检测变化区域）
- ✅ 增量更新模式（无变化时跳过帧）
- ✅ GPU 加速（~50 FPS）
- ✅ C 接口（支持 C++, Python 等）

**快速开始**：
```cpp
#include "DxgiGrab.h"

void* dxgi = dxgi_create();
// 捕获屏幕
dxgi_get_frame(dxgi, buffer, 100);
dxgi_destroy(dxgi);
```

**📖 详细文档**：[MirrorScreen/README.md](MirrorScreen/README.md) - API文档、性能数据、编译说明、使用示例

---

### 2️⃣ 超低带宽远程桌面系统

基于 DXGI 的完整远程桌面解决方案，位于 `RemoteDesktop/` 目录。

### 🌟 核心特性

- ✅ **XOR 差分编码**：当前帧与上一帧异或，压缩率高达 99.5%
- ✅ **脏矩形增量传输**：只传输变化区域
- ✅ **智能跳帧**：无变化时只发送 5 字节标记
- ✅ **数据压缩**：zlib 压缩大量 0 值，极致优化
- ✅ **Web 浏览器支持**：手机/平板无缝访问，MJPEG 流
- ✅ **实时统计**：FPS、带宽、跳帧率、XOR 压缩率监控
- ✅ **低延迟**：60fps 检测频率，TCP 传输

### 🚀 快速使用

**1. 启动被控端服务器**：
```bash
cd RemoteDesktop
python server.py
```

**2. 启动客户端（二选一）**：

**桌面客户端**：
```bash
# 本地测试
python client.py

# 远程连接
python client.py 192.168.1.100 9999
```

**Web 浏览器访问**：
```bash
python web_server.py
# 浏览器访问 http://192.168.x.x:5000
# 支持手机/平板/电脑浏览器
```

**3. 使用快捷键**：
- `Q / Esc`：退出
- `S`：保存截图

### 📊 性能表现

| 版本 | 带宽 | 优化率 | 核心技术 |
|------|------|--------|----------|
| v1.0 全屏传输 | 89 MB/s | - | 完整帧 + zlib |
| v2.0 脏矩形 | 60 MB/s | 33% | 脏矩形增量传输 |
| v3.0 XOR 优化 | **0.4 MB/s** | **99.6%** ✨ | XOR 差分 + zlib |

**实测数据（1920x1080, 20fps）**：
- 动态场景：0.4 MB/s
- 静态场景：0.11 MB/s（110 KB/s）
- XOR 压缩率：98-99.5%
- 显示延迟：< 50ms

**📖 详细文档**：[RemoteDesktop/README.md](RemoteDesktop/README.md) - 完整使用指南、优化原理、性能测试

---

## 📁 项目结构

```
DXGI-ScreenCapture-DLL/
├── DxgiGrab3.dll              # 最新版 DLL（v3.0，推荐使用）
├── DxgiGrab2.dll              # v2.0 DLL
├── DxgiGrab.dll               # v1.0 DLL
├── MirrorScreen/              # DLL 源码和测试
│   ├── MirrorScreen/          # C++ 源码
│   │   ├── DxgiGrab.h        # C API 头文件
│   │   ├── DxgiGrab.cpp      # 实现文件
│   │   └── MirrorScreen.vcxproj
│   ├── test/                  # C++ 测试项目
│   │   ├── test.cpp          # 基础全屏测试
│   │   └── test_dirty_rect.cpp # 脏矩形测试
│   ├── README.md              # 📖 DLL 详细文档（API、性能、编译）
│   ├── 1.py                   # Python 基础测试
│   ├── 2.py                   # Python 优化测试（推荐）
│   └── 新版dxgi脏矩形局部更新.py  # 增强版本
├── RemoteDesktop/             # 🆕 远程桌面系统（v3.0 - XOR 优化版）
│   ├── protocol.py            # 通信协议（支持 XOR 数据包）
│   ├── server.py              # 被控端服务器（XOR 编码）
│   ├── client.py              # 桌面客户端（tkinter GUI + XOR 解码）
│   ├── web_server.py          # Web 服务器（Flask + MJPEG + XOR 解码）
│   ├── README.md              # 远程桌面详细文档
│   ├── start_server.ps1       # 服务器启动脚本
│   └── start_client.ps1       # 客户端启动脚本
├── README.md                  # 本文档（项目概览）
└── DIRTY_RECT_USAGE.md       # 脏矩形详细使用文档
```

## 🚀 快速开始

### DLL 使用

查看 [MirrorScreen/README.md](MirrorScreen/README.md) 获取：
- API 完整文档
- C++/Python 使用示例
- 编译和测试指南
- 性能数据和优化建议

### 远程桌面使用

查看 [RemoteDesktop/README.md](RemoteDesktop/README.md) 获取：
- 完整安装和使用指南
- 桌面客户端和 Web 浏览器访问
- XOR 优化原理和性能测试
- 配置调整和故障排查

## 📊 性能亮点

## 📊 性能亮点

### DLL 性能（1920x1080）

- 🚀 检测速率：60 fps（动态场景）/ 17-19 fps（静态场景，自动节能）
- 💾 数据节省：脏矩形模式平均节省 **70-80%** 数据量
- 🔋 CPU 占用：前台 10-15%（i7 4代）
- 🎮 GPU 占用：前台 15-20%（GTX 1050Ti）

### RemoteDesktop 性能（1920x1080, 20fps）

| 指标 | 数值 |
|------|------|
| 动态场景带宽 | **0.4 MB/s** ⚡ |
| 静态场景带宽 | **0.11 MB/s** (110 KB/s) |
| XOR 压缩率 | **98-99.5%** |
| 显示延迟 | < 50ms |
| 优化效果 | 从 89 MB/s 降至 0.4 MB/s（**99.6% 节省**）|

## 🛠️ 技术栈

- **DXGI Desktop Duplication API**：GPU 加速屏幕捕获
- **Direct3D 11**：图形接口
- **Python**：远程桌面实现（socket, numpy, opencv, tkinter, Flask）
- **XOR 差分编码**：帧间差分，极致压缩
- **zlib**：通用数据压缩

## 📝 许可证

本项目基于 DXGI Desktop Duplication API 开发，仅供学习和研究使用。

## 📚 相关文档

**项目文档**：
- [MirrorScreen/README.md](MirrorScreen/README.md) - DLL 详细文档
- [RemoteDesktop/README.md](RemoteDesktop/README.md) - 远程桌面详细文档
- [DIRTY_RECT_USAGE.md](DIRTY_RECT_USAGE.md) - 脏矩形使用指南

**Microsoft 官方文档**：
- [DXGI Desktop Duplication API](https://docs.microsoft.com/en-us/windows/win32/direct3ddxgi/desktop-dup-api)
- [Direct3D 11](https://docs.microsoft.com/en-us/windows/win32/direct3d11/atoc-dx-graphics-direct3d-11)

---

**开发日期**：2026年2月13日  
**⭐ 如果这个项目对你有帮助，请给个星标支持！**


