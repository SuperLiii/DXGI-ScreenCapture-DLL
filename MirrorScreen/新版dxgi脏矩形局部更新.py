"""
DXGI屏幕捕获 - 简化版本
"""

import ctypes
import numpy as np
import cv2
import time
import threading
from pathlib import Path
from queue import Queue
import tkinter as tk
from PIL import Image, ImageTk

# 定义FrameStatus枚举
FS_OK = 0
FS_TIMEOUT = 1
FS_ERROR = 2

JCcount = 0

# 定义DirtyRect结构体
class DirtyRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int),
        ("top", ctypes.c_int),
        ("right", ctypes.c_int),
        ("bottom", ctypes.c_int)
    ]

class DxgiCapture:
    def __init__(self, dll_path="../DxgiGrab3.dll"):
        """初始化DXGI捕获
        
        Args:
            dll_path: DLL文件路径
        """
        # 加载DLL - 尝试多个可能的路径
        dll_file = Path(dll_path)
        
        if not dll_file.exists():
            # 尝试其他可能的路径
            for possible_path in [
                "DxgiGrab3.dll",
                "../DxgiGrab3.dll",
                "../../DxgiGrab3.dll",
                r"C:\Users\Administrator\Desktop\DXGI-ScreenCapture-DLL\DxgiGrab3.dll"
            ]:
                dll_file = Path(possible_path)
                if dll_file.exists():
                    break
            else:
                raise FileNotFoundError(f"找不到DLL文件，尝试过的路径: {dll_path}")
        
        self.dll = ctypes.CDLL(str(dll_file.absolute()))
        
        # 定义函数原型
        self.dll.dxgi_create.restype = ctypes.c_void_p
        self.dll.dxgi_create.argtypes = []
        
        self.dll.dxgi_destroy.restype = None
        self.dll.dxgi_destroy.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_width.restype = ctypes.c_int
        self.dll.dxgi_get_width.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_height.restype = ctypes.c_int
        self.dll.dxgi_get_height.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_size.restype = ctypes.c_int
        self.dll.dxgi_get_size.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_frame.restype = ctypes.c_int
        self.dll.dxgi_get_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_int]
        
        # 定义脏矩形相关API
        self.dll.dxgi_acquire_frame.restype = ctypes.c_int
        self.dll.dxgi_acquire_frame.argtypes = [ctypes.c_void_p, ctypes.c_int]
        
        self.dll.dxgi_release_frame.restype = None
        self.dll.dxgi_release_frame.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_dirty_rects_count.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_rects_count.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_dirty_rects.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_rects.argtypes = [ctypes.c_void_p, ctypes.POINTER(DirtyRect), ctypes.c_int]
        
        self.dll.dxgi_get_dirty_region_size.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_region_size.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_copy_dirty_regions.restype = ctypes.c_int
        self.dll.dxgi_copy_dirty_regions.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_int]
        
        self.dll.dxgi_copy_acquired_frame.restype = ctypes.c_int
        self.dll.dxgi_copy_acquired_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char)]
        
        # 创建DXGI实例
        self.dxgi = self.dll.dxgi_create()
        if not self.dxgi:
            raise RuntimeError("创建DXGI实例失败")
        
        # 获取屏幕信息
        self.width = self.dll.dxgi_get_width(self.dxgi)
        self.height = self.dll.dxgi_get_height(self.dxgi)
        self.size = self.dll.dxgi_get_size(self.dxgi)
        
        # 创建缓冲区
        self.buffer = (ctypes.c_char * self.size)()
        
    def capture(self, timeout_ms=100):
        """捕获一帧
        
        Args:
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            tuple: (status, frame) status为FS_OK时返回numpy数组，否则为None
        """
        status = self.dll.dxgi_get_frame(self.dxgi, self.buffer, timeout_ms)
        
        if status == FS_OK:
            # 将缓冲区转换为numpy数组 (BGRA格式)
            frame = np.frombuffer(self.buffer, dtype=np.uint8)
            frame = frame.reshape(self.height, self.width, 4)
            # 转换为BGR格式 (OpenCV使用BGR)
            frame = frame[:, :, :3]  # 去掉Alpha通道
            return status, frame
        
        return status, None
    
    def capture_dirty_rects(self, timeout_ms=100):
        """使用脏矩形方式捕获帧（只在有变化时获取完整帧）
        
        Args:
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            tuple: (status, frame, dirty_info) 
                   dirty_info包含 {'count': int, 'rects': list, 'size': int, 'saved_percent': float}
                   如果没有变化，frame为None
        """
        # 先获取帧以检测脏矩形
        status = self.dll.dxgi_acquire_frame(self.dxgi, timeout_ms)

        global JCcount
        JCcount += 1

        if status != FS_OK:
            return status, None, None
        


        try:
            # 获取脏矩形数量
            dirty_count = self.dll.dxgi_get_dirty_rects_count(self.dxgi)
            
            dirty_info = {
                'count': dirty_count,
                'rects': [],
                'size': 0,
                'saved_percent': 100.0  # 默认100%节省（无变化）
            }
            
            # 如果没有变化，释放帧后返回
            if dirty_count == 0:
                self.dll.dxgi_release_frame(self.dxgi)
                return FS_OK, None, dirty_info
            
            # 有变化时，获取脏矩形详细信息
            rects_array = (DirtyRect * dirty_count)()
            self.dll.dxgi_get_dirty_rects(self.dxgi, rects_array, dirty_count)
            
            # 转换为Python列表
            dirty_info['rects'] = [
                {
                    'left': r.left,
                    'top': r.top,
                    'right': r.right,
                    'bottom': r.bottom,
                    'width': r.right - r.left,
                    'height': r.bottom - r.top
                }
                for r in rects_array
            ]
            
            # 获取脏区域大小
            dirty_size = self.dll.dxgi_get_dirty_region_size(self.dxgi)
            dirty_info['size'] = dirty_size
            dirty_info['saved_percent'] = (1.0 - dirty_size / self.size) * 100.0 if self.size > 0 else 0.0
            
            # 只有变化时才获取完整帧（使用已acquired的帧）
            status_frame = self.dll.dxgi_copy_acquired_frame(self.dxgi, self.buffer)
            
            if status_frame == FS_OK:
                frame = np.frombuffer(self.buffer, dtype=np.uint8).copy()
                frame = frame.reshape(self.height, self.width, 4)
                frame = frame[:, :, :3]
                return FS_OK, frame, dirty_info
            
        finally:
            # 释放帧
            self.dll.dxgi_release_frame(self.dxgi)
        
        return FS_ERROR, None, None
    
    def __del__(self):
        """释放资源"""
        if hasattr(self, 'dxgi') and self.dxgi:
            self.dll.dxgi_destroy(self.dxgi)

def capture_thread(capture, frame_queue, stop_event):
    """捕获线程 - 持续捕获屏幕帧（使用脏矩形优化）"""
    last_valid_frame = None
    
    # 跳过第一帧（DXGI第一帧通常是黑的）
    capture.capture(timeout_ms=1000)
    
    # 获取初始帧
    status, frame = capture.capture(timeout_ms=1000)
    if status == FS_OK and frame is not None:
        last_valid_frame = frame
        try:
            frame_queue.put_nowait(frame)
        except:
            pass
    
    while not stop_event.is_set():
        try:
            status, frame, dirty_info = capture.capture_dirty_rects(timeout_ms=16)
            
            if status == FS_OK and dirty_info is not None:
                if dirty_info['count'] > 0 and frame is not None:
                    last_valid_frame = frame
                    # 如果队列满了，移除旧帧
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                        except:
                            pass
                    try:
                        frame_queue.put_nowait(frame)
                    except:
                        pass
            
            # 限制最大检测频率为60fps，降低动态场景下的CPU/GPU占用
            time.sleep(0.008)
                    
        except Exception:
            break

def main():
    """主函数"""
    try:
        # 创建捕获实例
        capture = DxgiCapture()
        
        # 创建线程通信对象
        frame_queue = Queue(maxsize=2)
        stop_event = threading.Event()
        
        # 启动捕获线程
        capture_worker = threading.Thread(
            target=capture_thread,
            args=(capture, frame_queue, stop_event),
            daemon=True
        )
        capture_worker.start()
        
        # 创建tkinter窗口
        root = tk.Tk()
        root.title("DXGI Screen Capture")
        
        # 计算显示尺寸
        display_width = 1280
        display_height = int(display_width * capture.height / capture.width)
        
        # 创建Canvas用于显示图像
        canvas = tk.Canvas(root, width=display_width, height=display_height, bg='black')
        canvas.pack()
        
        photo_image = None
        last_frame_id = None
        
        def on_timer():
            """1秒定时器"""
            global JCcount
            if not stop_event.is_set():
                # 在这里添加需要每秒执行的代码
                print("检测", JCcount)
                JCcount = 0
                
                # 继续下一次定时
                root.after(1000, on_timer)
        
        def update_frame():
            """更新帧显示"""
            nonlocal photo_image, last_frame_id
            
            if stop_event.is_set():
                return
            
            has_new_frame = False
            
            try:
                frame = frame_queue.get_nowait()
                
                if frame is not None:
                    frame_id = id(frame)
                    
                    if frame_id != last_frame_id:
                        last_frame_id = frame_id
                        has_new_frame = True
                        
                        # BGR转RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # 调整大小
                        frame_resized = cv2.resize(frame_rgb, (display_width, display_height))
                        
                        # 转换为PIL Image
                        img = Image.fromarray(frame_resized)
                        photo_image = ImageTk.PhotoImage(image=img)
                        
                        # 更新Canvas
                        canvas.delete("all")
                        canvas.create_image(0, 0, anchor=tk.NW, image=photo_image)
            except:
                pass
            
            # 动态刷新间隔：有新帧时快速刷新，无新帧时降低频率
            next_interval = 33 if has_new_frame else 100
            root.after(next_interval, update_frame)
        
        def on_key_press(event):
            """键盘事件处理"""
            if event.char == 'q' or event.keysym == 'Escape':
                on_closing()
            elif event.char == 's':
                # 保存截图
                try:
                    frame = frame_queue.get_nowait()
                    filename = f"screenshot_{int(time.time())}.png"
                    cv2.imwrite(filename, frame)
                except:
                    pass
        
        def on_closing():
            """窗口关闭事件"""
            stop_event.set()
            capture_worker.join(timeout=1)
            root.quit()
            root.destroy()
        
        # 绑定事件
        root.bind('<KeyPress>', on_key_press)
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 启动定时器
        root.after(1000, on_timer)
        
        # 启动帧更新
        root.after(100, update_frame)
        
        # 启动主循环
        root.mainloop()
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
