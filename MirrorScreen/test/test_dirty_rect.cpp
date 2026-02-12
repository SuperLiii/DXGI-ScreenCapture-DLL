// 脏矩形功能测试示例
// 演示如何使用DXGI脏矩形API进行增量屏幕捕获

#include <Windows.h>
#include <iostream>
#include <vector>
#include "../MirrorScreen/DxgiGrab.h"

void test_full_frame_capture() {
    printf("=== 测试全屏捕获 ===\n");
    
    void* dxgi = dxgi_create();
    if (!dxgi) {
        printf("创建DXGI失败\n");
        return;
    }
    
    int width = dxgi_get_width(dxgi);
    int height = dxgi_get_height(dxgi);
    int size = dxgi_get_size(dxgi);
    
    printf("屏幕尺寸: %dx%d\n", width, height);
    printf("帧大小: %d 字节 (%.2f MB)\n", size, size / 1024.0 / 1024.0);
    
    char* frameBuffer = (char*)malloc(size);
    
    // 捕获一帧
    FrameStatus status = dxgi_get_frame(dxgi, frameBuffer, 1000);
    if (status == FS_OK) {
        printf("✓ 成功捕获完整帧\n");
    } else {
        printf("✗ 捕获失败: %d\n", status);
    }
    
    free(frameBuffer);
    dxgi_destroy(dxgi);
}

void test_dirty_rect_capture() {
    printf("\n=== 测试脏矩形捕获 ===\n");
    
    void* dxgi = dxgi_create();
    if (!dxgi) {
        printf("创建DXGI失败\n");
        return;
    }
    
    int fullSize = dxgi_get_size(dxgi);
    printf("完整帧大小: %d 字节\n", fullSize);
    
    int frameCount = 0;
    int totalDirtySize = 0;
    int totalDirtyRects = 0;
    
    printf("\n开始监控屏幕变化 (移动鼠标或打开窗口以产生变化)...\n");
    printf("按Ctrl+C退出\n\n");
    
    for (int i = 0; i < 100; i++) {
        // 获取帧
        FrameStatus status = dxgi_acquire_frame(dxgi, 100);
        
        if (status == FS_TIMEOUT) {
            printf("[%03d] 超时 - 无新帧\n", i);
            continue;
        }
        
        if (status == FS_ERROR) {
            printf("[%03d] 错误\n", i);
            break;
        }
        
        // 获取脏矩形数量
        int dirtyCount = dxgi_get_dirty_rects_count(dxgi);
        
        if (dirtyCount > 0) {
            frameCount++;
            
            // 获取脏矩形数据
            std::vector<DirtyRect> rects(dirtyCount);
            dxgi_get_dirty_rects(dxgi, rects.data(), dirtyCount);
            
            // 获取脏区域总大小
            int dirtySize = dxgi_get_dirty_region_size(dxgi);
            
            totalDirtySize += dirtySize;
            totalDirtyRects += dirtyCount;
            
            float savePercent = (1.0f - (float)dirtySize / fullSize) * 100.0f;
            
            printf("[%03d] 检测到 %d 个脏矩形, 总大小: %d 字节 (节省 %.1f%%)\n",
                i, dirtyCount, dirtySize, savePercent);
            
            // 打印每个脏矩形的详细信息
            for (int j = 0; j < dirtyCount && j < 5; j++) {  // 最多显示5个
                int w = rects[j].right - rects[j].left;
                int h = rects[j].bottom - rects[j].top;
                printf("      矩形[%d]: 位置(%d,%d) 大小(%dx%d) = %d 字节\n",
                    j, rects[j].left, rects[j].top, w, h, w * h * 4);
            }
            if (dirtyCount > 5) {
                printf("      ... 还有 %d 个矩形\n", dirtyCount - 5);
            }
            
            // 复制脏区域数据
            std::vector<char> dirtyBuffer(dirtySize);
            status = dxgi_copy_dirty_regions(dxgi, dirtyBuffer.data(), dirtySize);
            
            if (status == FS_OK) {
                // 这里可以进行网络传输
                // send_to_network(dirtyCount, rects.data(), dirtyBuffer.data(), dirtySize);
            }
        } else {
            printf("[%03d] 无变化\n", i);
        }
        
        // 释放帧
        dxgi_release_frame(dxgi);
        
        Sleep(100);  // 每100ms检测一次
    }
    
    // 统计信息
    printf("\n=== 统计信息 ===\n");
    printf("有效帧数: %d\n", frameCount);
    printf("脏矩形总数: %d\n", totalDirtyRects);
    printf("脏数据总量: %d 字节 (%.2f MB)\n", totalDirtySize, totalDirtySize / 1024.0 / 1024.0);
    
    if (frameCount > 0) {
        int potentialFullSize = fullSize * frameCount;
        float avgSavePercent = (1.0f - (float)totalDirtySize / potentialFullSize) * 100.0f;
        printf("如果传输完整帧: %d 字节 (%.2f MB)\n", 
            potentialFullSize, potentialFullSize / 1024.0 / 1024.0);
        printf("平均节省比例: %.1f%%\n", avgSavePercent);
    }
    
    dxgi_destroy(dxgi);
}

void test_hybrid_mode() {
    printf("\n=== 测试混合模式 (首帧全屏 + 增量更新) ===\n");
    
    void* dxgi = dxgi_create();
    if (!dxgi) {
        printf("创建DXGI失败\n");
        return;
    }
    
    int fullSize = dxgi_get_size(dxgi);
    std::vector<char> fullFrame(fullSize);
    bool firstFrame = true;
    
    printf("开始捕获...\n\n");
    
    for (int i = 0; i < 50; i++) {
        if (firstFrame) {
            // 发送完整帧
            FrameStatus status = dxgi_get_frame(dxgi, fullFrame.data(), 1000);
            if (status == FS_OK) {
                printf("[%03d] 发送完整帧: %d 字节\n", i, fullSize);
                // TODO: send_full_frame(fullFrame.data(), fullSize);
                firstFrame = false;
            }
        } else {
            // 发送脏矩形
            FrameStatus status = dxgi_acquire_frame(dxgi, 100);
            
            if (status == FS_OK) {
                int dirtyCount = dxgi_get_dirty_rects_count(dxgi);
                
                if (dirtyCount > 0) {
                    std::vector<DirtyRect> rects(dirtyCount);
                    dxgi_get_dirty_rects(dxgi, rects.data(), dirtyCount);
                    
                    int dirtySize = dxgi_get_dirty_region_size(dxgi);
                    std::vector<char> dirtyData(dirtySize);
                    dxgi_copy_dirty_regions(dxgi, dirtyData.data(), dirtySize);
                    
                    float savePercent = (1.0f - (float)dirtySize / fullSize) * 100.0f;
                    
                    printf("[%03d] 发送增量: %d 个矩形, %d 字节 (节省 %.1f%%)\n",
                        i, dirtyCount, dirtySize, savePercent);
                    
                    // TODO: send_dirty_rects(dirtyCount, rects.data(), dirtyData.data(), dirtySize);
                } else {
                    printf("[%03d] 无变化 - 跳过传输\n", i);
                }
                
                dxgi_release_frame(dxgi);
            } else if (status == FS_TIMEOUT) {
                printf("[%03d] 超时\n", i);
            }
        }
        
        Sleep(100);
    }
    
    dxgi_destroy(dxgi);
}

int main() {
    printf("DXGI 脏矩形功能测试\n");
    printf("====================\n\n");
    
    // 测试1: 全屏捕获
    test_full_frame_capture();
    
    Sleep(1000);
    
    // 测试2: 脏矩形捕获
    test_dirty_rect_capture();
    
    Sleep(1000);
    
    // 测试3: 混合模式
    test_hybrid_mode();
    
    printf("\n所有测试完成！\n");
    
    system("pause");
    return 0;
}
