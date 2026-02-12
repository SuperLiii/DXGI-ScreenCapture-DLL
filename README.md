# DXGI-ScreenCapture-DLL

基于DXGI Desktop Duplication API的高性能屏幕捕获DLL，支持全屏捕获和脏矩形增量捕获。

## 功能特性

### ✅ 已实现功能

- **全屏捕获**：捕获完整屏幕画面（BGRA格式）
- **脏矩形捕获**（新增）：只获取屏幕变化区域，大幅减少数据量
- **高性能**：基于GPU加速的DXGI API
- **C接口**：支持多语言调用

### 📋 适用场景

- 远程桌面传输
- 屏幕录制
- 实时屏幕共享
- 屏幕监控

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

### 脏矩形增量捕获示例

```cpp
#include "DxgiGrab.h"
#include <vector>

void* dxgi = dxgi_create();

while (running) {
    // 获取帧
    if (dxgi_acquire_frame(dxgi, 100) == FS_OK) {
        // 检查脏矩形
        int count = dxgi_get_dirty_rects_count(dxgi);
        if (count > 0) {
            // 获取脏矩形坐标
            std::vector<DirtyRect> rects(count);
            dxgi_get_dirty_rects(dxgi, rects.data(), count);
            
            // 获取脏区域数据
            int dirtySize = dxgi_get_dirty_region_size(dxgi);
            std::vector<char> data(dirtySize);
            dxgi_copy_dirty_regions(dxgi, data.data(), dirtySize);
            
            // 网络传输 rects + data
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

### 脏矩形 API（新增）

| 函数 | 说明 |
|------|------|
| `dxgi_acquire_frame()` | 获取帧（只获取元数据） |
| `dxgi_release_frame()` | 释放帧 |
| `dxgi_get_dirty_rects_count()` | 获取脏矩形数量 |
| `dxgi_get_dirty_rects()` | 获取脏矩形坐标数据 |
| `dxgi_get_dirty_region_size()` | 获取脏区域总大小 |
| `dxgi_copy_dirty_regions()` | 复制脏区域像素数据 |

详细使用说明请参考 [DIRTY_RECT_USAGE.md](DIRTY_RECT_USAGE.md)

## 性能优势

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

- 基础测试：运行 `test` 项目
- 脏矩形测试：编译并运行 `test_dirty_rect.cpp`

## 项目结构

```
DXGI-ScreenCapture-DLL/
├── MirrorScreen/
│   ├── MirrorScreen/          # DLL 源码
│   │   ├── DxgiGrab.h        # 头文件
│   │   ├── DxgiGrab.cpp      # 实现文件
│   │   └── MirrorScreen.vcxproj
│   └── test/                  # 测试项目
│       ├── test.cpp          # 基础测试
│       └── test_dirty_rect.cpp # 脏矩形测试
├── README.md
└── DIRTY_RECT_USAGE.md       # 详细使用文档
```

## 技术细节

- **API**：DXGI Desktop Duplication API
- **图形接口**：Direct3D 11
- **像素格式**：BGRA（每像素4字节）
- **坐标系统**：左上角为原点(0,0)

## 远程传输建议流程

1. **首次连接**：发送完整帧（`dxgi_get_frame`）
2. **增量更新**：发送脏矩形（`dxgi_acquire_frame` + `dxgi_copy_dirty_regions`）
3. **无变化时**：不传输数据（`dirty_count == 0`）
4. **可选优化**：
   - 异或差分压缩
   - Zlib/LZ4 压缩
   - 帧率动态调整


