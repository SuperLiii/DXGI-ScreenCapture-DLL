# DXGI-ScreenCapture-DLL

基于DXGI Desktop Duplication API的高性能屏幕捕获DLL，支持全屏捕获和脏矩形增量捕获。

## 功能特性

### ✅ 已实现功能

- **全屏捕获**：捕获完整屏幕画面（BGRA格式）
- **脏矩形检测**：实时检测屏幕变化区域
- **增量更新模式**：只在有变化时传输数据，无变化时跳过帧
- **已获取帧复制**：从已acquired的帧直接复制数据，避免重复获取
- **高性能**：基于GPU加速的DXGI API，~50 FPS检测速率
- **C接口**：支持多语言调用（C++, Python等）

### 📋 适用场景

- 远程桌面传输（主要应用场景）
- 屏幕录制
- 实时屏幕共享
- 屏幕监控

### 🎯 最新版本（DxgiGrab3.dll）

- **发布日期**：2026年2月12日
- **主要更新**：
  - 新增 `dxgi_copy_acquired_frame()` API
  - 优化增量更新逻辑，避免重复acquire frame错误
  - 完善Python测试脚本，支持实时脏矩形可视化
  - 增强统计功能，显示数据节省量和跳帧统计

## 快速开始

### 全屏捕获示例

```cpp
#include "DxgiGrab.h"

void* dxgi = dxgi_create();
int size = dxgi_get_size(dxgi);
char* buffer = (char*)malloc(size);

// 捕获一帧
FrameStatus status = dxgi_get_frame(dxgi, buffer, 100);
if (status == FS_OK) {
    // 处理帧数据
}

free(buffer);
dxgi_destroy(dxgi);
```

### 脏矩形增量捕获示例（推荐用于远程桌面）

```cpp
#include "DxgiGrab.h"
#include <vector>

void* dxgi = dxgi_create();
int fullSize = dxgi_get_size(dxgi);
std::vector<char> fullFrame(fullSize);

while (running) {
    // 获取帧
    if (dxgi_acquire_frame(dxgi, 100) == FS_OK) {
        // 检查脏矩形
        int count = dxgi_get_dirty_rects_count(dxgi);
        
        if (count == 0) {
            // 无变化，跳过此帧，不传输数据
            dxgi_release_frame(dxgi);
            continue;
        }
        
        // 有变化，获取完整帧
        if (dxgi_copy_acquired_frame(dxgi, fullFrame.data()) == FS_OK) {
            // 获取脏矩形坐标
            std::vector<DirtyRect> rects(count);
            dxgi_get_dirty_rects(dxgi, rects.data(), count);
            
            // 网络传输: rects + fullFrame
            // 或只传输脏区域: 使用 dxgi_copy_dirty_regions()
        }
        
        dxgi_release_frame(dxgi);
    }
}

dxgi_destroy(dxgi);
```

## API 文档

### 基础 API

| 函数 | 说明 |
|------|------|
| `dxgi_create()` | 创建DXGI捕获实例 |
| `dxgi_destroy()` | 销毁实例 |
| `dxgi_get_width()` | 获取屏幕宽度 |
| `dxgi_get_height()` | 获取屏幕高度 |
| `dxgi_get_size()` | 获取完整帧大小（字节） |
| `dxgi_get_frame()` | 获取完整屏幕帧 |

### 脏矩形 API

| 函数 | 说明 |
|------|------|
| `dxgi_acquire_frame()` | 获取帧（只获取元数据，不复制像素） |
| `dxgi_release_frame()` | 释放帧 |
| `dxgi_get_dirty_rects_count()` | 获取脏矩形数量 |
| `dxgi_get_dirty_rects()` | 获取脏矩形坐标数据 |
| `dxgi_get_dirty_region_size()` | 获取脏区域总大小（字节） |
| `dxgi_copy_dirty_regions()` | 复制脏区域像素数据 |
| `dxgi_copy_acquired_frame()` | **[新增]** 复制已acquired的完整帧数据 |

详细使用说明请参考 [DIRTY_RECT_USAGE.md](DIRTY_RECT_USAGE.md)

## 🆕 远程桌面系统

基于 DXGI 屏幕捕获的完整远程桌面解决方案，位于 `RemoteDesktop/` 目录。

### 功能特性

- ✅ **脏矩形增量传输**：只传输变化区域，节省 80% 带宽
- ✅ **智能跳帧**：无变化时只发送 1 字节标记
- ✅ **数据压缩**：zlib 压缩，压缩比 60-80%
- ✅ **实时统计**：FPS、带宽、跳帧率监控
- ✅ **低延迟**：60fps 检测频率，TCP 传输

### 快速使用

**1. 启动被控端服务器**：
```bash
cd RemoteDesktop
python server.py
```

**2. 启动控制端客户端**：
```bash
# 本地测试
python client.py

# 远程连接
python client.py 192.168.1.100 9999
```

**3. 使用快捷键**：
- `Q / Esc`：退出
- `S`：保存截图

### 性能表现

| 指标 | 数值 |
|------|------|
| 平均带宽 | 50-80 MB/s（动态场景） |
| 节省带宽 | 87%（对比全屏传输） |
| 显示延迟 | < 50ms |
| 跳帧占比 | 40-60%（静态场景） |

详细文档请参考 [RemoteDesktop/README.md](RemoteDesktop/README.md)

## 性能数据

### 实测数据（1920x1080分辨率）

**测试环境（i7 4代 + GTX 1050Ti）**：

**检测频率**（2.py优化版）：
- 静态场景：17-19次/秒（DXGI自动节能）
- 动态场景：60次/秒（60fps限制）
- CPU占用：最小化 3%，前台 10-15%（优化后）
- GPU占用：最小化 3%，前台 15-20%（优化后）

**数据节省效果**：
- 全屏帧大小：7.91 MB/帧
- 脏矩形平均节省：**70.1%** 数据量
- 增量跳帧节省：**38.8%** 传输量
- 总体数据节省：**~80%**

**性能对比**：

| 模式 | 检测频率 | 数据量/秒 | 适用场景 |
|------|---------|----------|---------|
| 全屏传输（60 FPS） | 60 fps | ~475 MB/s | 高速游戏、视频播放 |
| 脏矩形传输（60 FPS） | 60 fps | ~142 MB/s | 一般应用操作 |
| 增量模式（优化版） | 动态60/静态17 | ~57 MB/s | 远程桌面（推荐） |

### 理论性能

假设 1920x1080 分辨率：

- **全屏传输**：~8 MB/帧
- **脏矩形传输**（10%变化区域）：~0.8 MB/帧
- **数据节省**：约 90%

实际节省比例取决于屏幕变化程度。

## 编译说明

### 环境要求

- Visual Studio 2017 或更高版本
- Windows SDK
- C++11 或更高版本

### 编译步骤

1. 打开 `MirrorScreen/MirrorScreen.sln`
2. 选择配置（Debug/Release）
3. 生成解决方案
4. DLL输出在 `x64/Release/` 或 `x64/Debug/`

### 测试

#### C++ 测试
- 基础测试：运行 `test` 项目
- 脏矩形测试：编译并运行 `test_dirty_rect.cpp`

#### Python 测试

**依赖安装**：
```bash
pip install numpy opencv-python pillow
```

**1.py - 基础全屏捕获测试**：
```bash
cd MirrorScreen
python 1.py
```
- 使用 tkinter 显示实时屏幕捕获
- 显示FPS统计
- 支持窗口拖动时持续更新
- 按 'q' 退出，按 's' 保存截图

**2.py - 优化版增量更新测试（推荐）**：
```bash
cd MirrorScreen
python 2.py
```
- ✅ 增量更新模式：只在有变化时传输帧
- ✅ 性能优化：60fps检测频率限制，降低CPU/GPU占用
- ✅ 动态刷新：有新帧30fps，无新帧10fps
- ✅ 检测频率监控：每秒输出检测次数
- ✅ 简洁界面：专注性能，移除统计开销
- 按 'q' 或 Esc 退出，按 's' 保存截图

**测试输出示例**：
```
检测 68   # 首帧初始化
检测 32   # 切换到脏矩形检测
检测 17   # 静态场景（DXGI自动节能）
检测 19
检测 60   # 动态场景（受60fps限制）
检测 61
```

## 项目结构

```
DXGI-ScreenCapture-DLL/
├── DxgiGrab3.dll              # 最新版DLL（含增量更新支持）
├── DxgiGrab2.dll              # 脏矩形版DLL
├── DxgiGrab.dll               # 基础版DLL
├── MirrorScreen/
│   ├── MirrorScreen/          # DLL 源码
│   │   ├── DxgiGrab.h        # C API头文件
│   │   ├── DxgiGrab.cpp      # 实现文件
│   │   └── MirrorScreen.vcxproj
│   ├── test/                  # C++ 测试项目
│   │   ├── test.cpp          # 基础全屏测试
│   │   └── test_dirty_rect.cpp # 脏矩形测试
│   ├── 1.py                   # Python基础测试（全屏捕获+tkinter显示）
│   ├── 2.py                   # Python优化测试（增量更新+性能优化）
│   └── 新版dxgi脏矩形局部更新.py  # 增强版本（120fps检测）
├── RemoteDesktop/             # 🆕 远程桌面系统
│   ├── protocol.py            # 通信协议定义
│   ├── server.py              # 被控端服务器
│   ├── client.py              # 控制端客户端
│   ├── README.md              # 远程桌面文档
│   ├── start_server.ps1       # 服务器启动脚本
│   └── start_client.ps1       # 客户端启动脚本
├── README.md                  # 本文档
└── DIRTY_RECT_USAGE.md       # 脏矩形详细使用文档
```

## 技术细节

- **API**：DXGI Desktop Duplication API
- **图形接口**：Direct3D 11
- **像素格式**：BGRA（每像素4字节）
- **坐标系统**：左上角为原点(0,0)

### 重要注意事项

⚠️ **DXGI 第一帧问题**：
- DXGI API的第一帧通常返回全黑图像
- 建议初始化后跳过第一帧
- Python脚本已自动处理此问题

⚠️ **Frame Acquire/Release 配对**：
- 每次 `dxgi_acquire_frame()` 必须配对 `dxgi_release_frame()`
- 未释放的帧会导致后续捕获失败（FS_ERROR）
- 建议使用RAII或try-finally确保释放

⚠️ **多线程使用**：
- DXGI实例不是线程安全的
- 建议每个线程创建独立的DXGI实例
- 或使用互斥锁保护访问

### 性能优化建议

1. **限制检测频率**：使用 `time.sleep(0.016)` 限制为60fps，降低50% CPU/GPU占用
2. **动态刷新策略**：GUI有新帧时30fps，无新帧时10fps
3. **DXGI自动节能**：静态场景时API自动阻塞，降至17-19次/秒检测
4. **降低捕获分辨率**：可以创建缩放的纹理
5. **压缩算法**：LZ4速度快，Zlib压缩率高
6. **批量传输**：多个小脏矩形合并传输
7. **GPU加速编码**：使用硬件编码器（H264/H265）

## 远程桌面传输推荐流程

### 增量更新模式（推荐）

```
1. 首次连接：
   - 使用 dxgi_get_frame() 发送完整帧作为基准

2. 持续监控：
   - 使用 dxgi_acquire_frame() 获取帧
   - 检查 dxgi_get_dirty_rects_count()
   
3. 分情况处理：
   a) dirty_count == 0（无变化）：
      - dxgi_release_frame()
      - 不发送任何数据
      - 节省带宽 ~8 MB/帧
      
   b) dirty_count > 0（有变化）：
      - dxgi_copy_acquired_frame() 复制完整帧
      - 或 dxgi_copy_dirty_regions() 只复制变化区域
      - 发送 dirty_rects + 数据
      - dxgi_release_frame()

4. 可选优化：
   - 脏矩形区域压缩（Zlib/LZ4）
   - 帧间差分（XOR）
   - 动态帧率调整
   - 质量自适应
```

### 数据传输格式建议

```cpp
// 数据包结构
struct FramePacket {
    uint32_t frameType;     // 0=跳过, 1=完整帧, 2=脏矩形
    uint32_t dirtyCount;    // 脏矩形数量
    DirtyRect rects[];      // 脏矩形坐标数组
    char data[];            // 像素数据（完整帧或脏区域）
};
```

### 带宽估算

- **传统全屏方案**：7.91 MB × 60 FPS = **475 MB/s**
- **增量更新方案**：7.91 MB × 60 FPS × 40% × 30% = **~57 MB/s**
- **节省带宽**：**~88%**

*备注：40%为有变化帧率，30%为脏矩形区域占比*

## 更新日志

### v3.0（DxgiGrab3.dll）- 2026年2月13日

**新增功能**：
- ✅ 新增 `dxgi_copy_acquired_frame()` API
- ✅ 增量更新模式：只在检测到变化时传输数据
- ✅ 完整的Python测试框架（1.py, 2.py）
- ✅ 检测频率监控：实时显示每秒检测次数

**修复问题**：
- 🔧 修复重复acquire frame导致的错误
- 🔧 修复DXGI第一帧黑屏问题
- 🔧 优化frame acquire/release配对逻辑

**性能优化**（2.py v2）：
- ⚡ 60fps检测频率限制：降低动态场景50% CPU/GPU占用
- ⚡ 动态GUI刷新：有帧30fps，无帧10fps
- ⚡ DXGI自动节能：静态场景17-19次/秒
- ⚡ 数据传输节省：~80%（典型使用场景）
- ⚡ 带宽占用降低：88%（对比全屏传输）
- ⚡ 前台CPU占用：从20%降至10-15%（i7 4代）

### v2.0（DxgiGrab2.dll）

**新增功能**：
- 脏矩形检测API
- 脏区域数据复制

### v1.0（DxgiGrab.dll）

**基础功能**：
- 全屏捕获
- 基本API接口

## 许可证

本项目基于 DXGI Desktop Duplication API 开发，仅供学习和研究使用。

## 相关链接

- [Microsoft DXGI Desktop Duplication 文档](https://docs.microsoft.com/en-us/windows/win32/direct3ddxgi/desktop-dup-api)
- [Direct3D 11 文档](https://docs.microsoft.com/en-us/windows/win32/direct3d11/atoc-dx-graphics-direct3d-11)

## 作者

开发日期：2026年2月

---

**⭐ 如果这个项目对你有帮助，请给个星标支持！**


