# DXGI 屏幕捕获 - 脏矩形功能使用说明

## 功能概述

本DLL已扩展支持DXGI脏矩形（Dirty Rectangles）功能，可以只获取和传输屏幕上发生变化的区域，大幅减少网络传输数据量。

## API 说明

### 基础功能（保留）

```c
// 创建DXGI捕获实例
void* dxgi_create(void);

// 销毁实例
void dxgi_destroy(void* pDxgi);

// 获取屏幕尺寸信息
int dxgi_get_width(void* pDxgi);
int dxgi_get_height(void* pDxgi);
int dxgi_get_size(void* pDxgi);  // 返回完整帧大小（宽*高*4字节）

// 获取完整屏幕帧（全屏截图）
FrameStatus dxgi_get_frame(void* pDxgi, char* pOut, int timeoutInMs);
```

### 新增脏矩形功能

```c
// 1. 获取帧（只获取元数据，不复制像素数据）
FrameStatus dxgi_acquire_frame(void* pDxgi, int timeoutInMs);

// 2. 释放帧（与acquire_frame配对使用）
void dxgi_release_frame(void* pDxgi);

// 3. 获取脏矩形数量
int dxgi_get_dirty_rects_count(void* pDxgi);

// 4. 获取脏矩形数据
int dxgi_get_dirty_rects(void* pDxgi, DirtyRect* pRects, int maxCount);

// 5. 获取所有脏区域的总大小（字节）
int dxgi_get_dirty_region_size(void* pDxgi);

// 6. 仅复制脏区域的像素数据
FrameStatus dxgi_copy_dirty_regions(void* pDxgi, char* pOut, int bufferSize);
```

### DirtyRect 结构体

```c
struct DirtyRect {
    int left;
    int top;
    int right;
    int bottom;
};
```

## 使用方式

### 方式一：全屏捕获（原有方式）

适用于需要完整屏幕画面的场景（如首帧传输）。

```cpp
#include "../MirrorScreen/DxgiGrab.h"
#include <Windows.h>
#include <stdio.h>

int main() {
    // 创建DXGI实例
    void* dxgi = dxgi_create();
    if (!dxgi) {
        printf("Failed to create DXGI\n");
        return 1;
    }
    
    // 分配完整帧缓冲区
    int frameSize = dxgi_get_size(dxgi);
    char* frameBuffer = (char*)malloc(frameSize);
    
    // 获取完整帧
    FrameStatus status = dxgi_get_frame(dxgi, frameBuffer, 100);
    if (status == FS_OK) {
        // 处理完整帧数据
        printf("Full frame captured: %d bytes\n", frameSize);
        // TODO: 网络传输 frameBuffer
    }
    
    free(frameBuffer);
    dxgi_destroy(dxgi);
    return 0;
}
```

### 方式二：脏矩形增量捕获（新增方式）

适用于远程桌面等需要持续传输的场景，只传输变化区域。

```cpp
#include "../MirrorScreen/DxgiGrab.h"
#include <Windows.h>
#include <stdio.h>
#include <vector>

int main() {
    void* dxgi = dxgi_create();
    if (!dxgi) {
        printf("Failed to create DXGI\n");
        return 1;
    }
    
    while (true) {
        // 1. 获取帧（不复制像素数据）
        FrameStatus status = dxgi_acquire_frame(dxgi, 100);
        
        if (status == FS_TIMEOUT) {
            continue; // 没有新帧，继续等待
        }
        
        if (status == FS_ERROR) {
            printf("Error acquiring frame\n");
            break;
        }
        
        // 2. 获取脏矩形信息
        int dirtyCount = dxgi_get_dirty_rects_count(dxgi);
        printf("Dirty rectangles count: %d\n", dirtyCount);
        
        if (dirtyCount > 0) {
            // 3. 读取脏矩形坐标
            std::vector<DirtyRect> dirtyRects(dirtyCount);
            dxgi_get_dirty_rects(dxgi, dirtyRects.data(), dirtyCount);
            
            // 打印脏矩形信息
            for (int i = 0; i < dirtyCount; i++) {
                printf("  Rect[%d]: (%d,%d) - (%d,%d), size: %dx%d\n", 
                    i,
                    dirtyRects[i].left, dirtyRects[i].top,
                    dirtyRects[i].right, dirtyRects[i].bottom,
                    dirtyRects[i].right - dirtyRects[i].left,
                    dirtyRects[i].bottom - dirtyRects[i].top);
            }
            
            // 4. 获取脏区域数据大小
            int dirtySize = dxgi_get_dirty_region_size(dxgi);
            printf("Total dirty region size: %d bytes\n", dirtySize);
            
            // 5. 复制脏区域像素数据
            std::vector<char> dirtyBuffer(dirtySize);
            status = dxgi_copy_dirty_regions(dxgi, dirtyBuffer.data(), dirtySize);
            
            if (status == FS_OK) {
                // 6. 网络传输
                // TODO: 发送 dirtyCount
                // TODO: 发送 dirtyRects 数组
                // TODO: 发送 dirtyBuffer 像素数据
                printf("Dirty regions copied successfully\n");
            }
        } else {
            printf("No dirty regions (screen not changed)\n");
        }
        
        // 7. 释放帧
        dxgi_release_frame(dxgi);
        
        Sleep(16); // ~60fps
    }
    
    dxgi_destroy(dxgi);
    return 0;
}
```

### 方式三：混合模式（推荐用于远程桌面）

首次发送完整帧，后续发送脏矩形增量。

```cpp
#include "../MirrorScreen/DxgiGrab.h"
#include <Windows.h>
#include <stdio.h>
#include <vector>

int main() {
    void* dxgi = dxgi_create();
    if (!dxgi) return 1;
    
    int frameSize = dxgi_get_size(dxgi);
    std::vector<char> fullFrame(frameSize);
    bool firstFrame = true;
    
    while (true) {
        if (firstFrame) {
            // 第一帧：发送完整画面
            FrameStatus status = dxgi_get_frame(dxgi, fullFrame.data(), 100);
            if (status == FS_OK) {
                printf("Sending full frame: %d bytes\n", frameSize);
                // TODO: 网络传输完整帧
                firstFrame = false;
            }
        } else {
            // 后续帧：只发送脏矩形
            FrameStatus status = dxgi_acquire_frame(dxgi, 100);
            
            if (status == FS_OK) {
                int dirtyCount = dxgi_get_dirty_rects_count(dxgi);
                
                if (dirtyCount > 0) {
                    // 获取脏矩形信息
                    std::vector<DirtyRect> rects(dirtyCount);
                    dxgi_get_dirty_rects(dxgi, rects.data(), dirtyCount);
                    
                    // 获取脏区域数据
                    int dirtySize = dxgi_get_dirty_region_size(dxgi);
                    std::vector<char> dirtyData(dirtySize);
                    dxgi_copy_dirty_regions(dxgi, dirtyData.data(), dirtySize);
                    
                    printf("Sending dirty regions: %d rects, %d bytes (saved %.1f%%)\n",
                        dirtyCount, dirtySize, 
                        (1.0 - (double)dirtySize / frameSize) * 100);
                    
                    // TODO: 网络传输脏矩形数据
                    // 格式：[矩形数量][矩形数组][像素数据]
                }
                
                dxgi_release_frame(dxgi);
            }
        }
        
        Sleep(16);
    }
    
    dxgi_destroy(dxgi);
    return 0;
}
```

## 网络传输数据格式建议

### 完整帧数据包

```
[包类型: 1字节=0x01] 
[宽度: 4字节] 
[高度: 4字节] 
[像素数据: 宽*高*4字节，BGRA格式]
```

### 脏矩形数据包

```
[包类型: 1字节=0x02] 
[矩形数量: 4字节] 
[矩形数组: 矩形数量*16字节]  // 每个矩形：left,top,right,bottom 各4字节
[像素数据: 变长]              // 所有矩形区域的像素数据，按顺序拼接
```

## 性能优化建议

1. **首帧使用全屏**：连接时发送完整帧，确保客户端有完整画面
2. **增量更新**：后续只发送脏矩形区域
3. **无变化时不传输**：`dirtyCount == 0` 时不发送数据包
4. **压缩优化**：对像素数据可以使用压缩算法（如zlib、lz4）进一步减小体积
5. **帧率控制**：根据网络情况动态调整捕获帧率

## 数据量对比

假设 1920x1080 分辨率：

- **全屏传输**：1920 × 1080 × 4 = 8,294,400 字节 ≈ 8MB
- **脏矩形传输**（假设只有 10% 区域变化）：≈ 800KB
- **节省比例**：约 90%

## 注意事项

1. `dxgi_acquire_frame` 和 `dxgi_release_frame` 必须配对使用
2. 在调用 `dxgi_copy_dirty_regions` 之前必须先调用 `dxgi_acquire_frame`
3. 如果屏幕没有变化，`dirtyCount` 可能为 0
4. 像素格式为 BGRA（每像素4字节）
5. 坐标系统：左上角为原点 (0,0)

## 编译说明

确保项目配置包含以下库：
- D3D11.lib
- DXGI.lib

Visual Studio 项目属性中需要包含 Windows SDK。
