/*
	作者：windpiaoxue
	联系方式：2977493715
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

#ifdef __cplusplus
extern "C" {
#endif
	API_DECLSPEC void	* dxgi_create(void);
	API_DECLSPEC void	  dxgi_destroy(void *);
	API_DECLSPEC int	  dxgi_get_size(void *);
	API_DECLSPEC int	  dxgi_get_width(void *);
	API_DECLSPEC int	  dxgi_get_height(void *);
	API_DECLSPEC FrameStatus dxgi_get_frame(void *, char *, int);
#ifdef __cplusplus
}
#endif