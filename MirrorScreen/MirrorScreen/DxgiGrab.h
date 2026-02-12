/*
	���ߣ�windpiaoxue
	��ϵ��ʽ��2977493715
*/

#pragma once

#ifdef _USRDLL
#define API_DECLSPEC  __declspec(dllexport)
#else
#define API_DECLSPEC  __declspec(dllimport)
#endif

enum FrameStatus
{
	FS_OK,
	FS_TIMEOUT,
	FS_ERROR,
};

// 矩形结构体，用于脏矩形
struct DirtyRect
{
	int left;
	int top;
	int right;
	int bottom;
};

#ifdef __cplusplus
extern "C" {
#endif
	// 基础功能
	API_DECLSPEC void	* dxgi_create(void);
	API_DECLSPEC void	  dxgi_destroy(void *);
	API_DECLSPEC int	  dxgi_get_size(void *);
	API_DECLSPEC int	  dxgi_get_width(void *);
	API_DECLSPEC int	  dxgi_get_height(void *);
	
	// 全屏截图（保留原有功能）
	API_DECLSPEC FrameStatus dxgi_get_frame(void *, char *, int);
	
	// 脏矩形功能
	API_DECLSPEC FrameStatus dxgi_acquire_frame(void *, int);                    // 获取帧（不复制数据）
	API_DECLSPEC void         dxgi_release_frame(void *);                        // 释放帧
	API_DECLSPEC int          dxgi_get_dirty_rects_count(void *);               // 获取脏矩形数量
	API_DECLSPEC int          dxgi_get_dirty_rects(void *, DirtyRect *, int);   // 获取脏矩形数据
	API_DECLSPEC int          dxgi_get_dirty_region_size(void *);               // 获取脏区域总大小
	API_DECLSPEC FrameStatus  dxgi_copy_dirty_regions(void *, char *, int);     // 仅复制脏区域数据
#ifdef __cplusplus
}
#endif