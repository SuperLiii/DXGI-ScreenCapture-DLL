"""
DXGI屏幕捕获测试
使用DxgiGrab.dll进行屏幕截图，并通过tkinter显示，同时显示FPS
使用tkinter解决拖动窗口时画面不更新的问题
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

class DxgiCapture:
    def __init__(self, dll_path="../DxgiGrab.dll"):
        """初始化DXGI捕获
        
        Args:
            dll_path: DLL文件路径
        """
        # 加载DLL
        dll_file = Path(dll_path)
        
        if not dll_file.exists():
            raise FileNotFoundError(f"找不到DLL文件: {dll_path}")
        
        print(f"加载DLL: {dll_file.absolute()}")
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
        
        # 创建DXGI实例
        self.dxgi = self.dll.dxgi_create()
        if not self.dxgi:
            raise RuntimeError("创建DXGI实例失败")
        
        # 获取屏幕信息
        self.width = self.dll.dxgi_get_width(self.dxgi)
        self.height = self.dll.dxgi_get_height(self.dxgi)
        self.size = self.dll.dxgi_get_size(self.dxgi)
        
        print(f"屏幕尺寸: {self.width}x{self.height}")
        print(f"帧大小: {self.size} 字节 ({self.size/1024/1024:.2f} MB)")
        
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
    
    def __del__(self):
        """释放资源"""
        if hasattr(self, 'dxgi') and self.dxgi:
            self.dll.dxgi_destroy(self.dxgi)
            print("DXGI实例已销毁")

def capture_thread(capture, frame_queue, stop_event, stats):
    """捕获线程 - 持续捕获屏幕帧
    
    Args:
        capture: DxgiCapture实例
        frame_queue: 帧队列
        stop_event: 停止事件
        stats: 统计信息字典
    """
    frame_count = 0
    start_time = time.time()
    
    while not stop_event.is_set():
        status, frame = capture.capture(timeout_ms=16)
        
        if status == FS_OK and frame is not None:
            frame_count += 1
            current_time = time.time()
            
            # 计算FPS
            elapsed = current_time - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            
            # 更新统计信息
            stats['fps'] = fps
            stats['frame_count'] = frame_count
            stats['elapsed'] = elapsed
            
            # 如果队列满了，移除旧帧
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except:
                    pass
            
            # 放入新帧
            try:
                frame_queue.put_nowait((frame, fps, frame_count))
            except:
                pass

def main():
    """主函数"""
    print("=" * 50)
    print("DXGI屏幕捕获测试 (按 'q' 或关闭窗口退出)")
    print("=" * 50)
    
    try:
        # 创建捕获实例
        capture = DxgiCapture()
        
        # 创建线程通信对象
        frame_queue = Queue(maxsize=2)
        stop_event = threading.Event()
        stats = {'fps': 0, 'frame_count': 0, 'elapsed': 0}
        
        # 启动捕获线程
        capture_worker = threading.Thread(
            target=capture_thread,
            args=(capture, frame_queue, stop_event, stats),
            daemon=True
        )
        capture_worker.start()
        
        print("\n开始捕获...\n")
        print("提示: 使用tkinter窗口，拖动时画面会持续更新")
        print()
        
        # 创建tkinter窗口
        root = tk.Tk()
        root.title("DXGI Screen Capture - Press 'q' or 'ESC' to quit")
        
        # 计算显示尺寸
        display_width = 1280
        display_height = int(display_width * capture.height / capture.width)
        
        # 创建Canvas用于显示图像
        canvas = tk.Canvas(root, width=display_width, height=display_height, bg='black')
        canvas.pack()
        
        # 创建信息标签
        info_frame = tk.Frame(root, bg='black')
        info_frame.pack(fill=tk.X)
        
        fps_label = tk.Label(info_frame, text="FPS: 0.00", fg='lime', bg='black', 
                            font=('Arial', 12, 'bold'))
        fps_label.pack(side=tk.LEFT, padx=10)
        
        resolution_label = tk.Label(info_frame, 
                                   text=f"Resolution: {capture.width}x{capture.height}",
                                   fg='white', bg='black', font=('Arial', 10))
        resolution_label.pack(side=tk.LEFT, padx=10)
        
        frames_label = tk.Label(info_frame, text="Frames: 0", fg='white', bg='black',
                               font=('Arial', 10))
        frames_label.pack(side=tk.LEFT, padx=10)
        
        status_label = tk.Label(info_frame, text="Status: Running", fg='lightgreen',
                               bg='black', font=('Arial', 9))
        status_label.pack(side=tk.LEFT, padx=10)
        
        photo_image = None
        
        def update_frame():
            """更新帧显示"""
            nonlocal photo_image
            
            if stop_event.is_set():
                return
            
            try:
                # 尝试获取最新帧
                frame, fps, frame_count = frame_queue.get_nowait()
                
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
                
                # 更新信息标签
                fps_label.config(text=f"FPS: {fps:.2f}")
                frames_label.config(text=f"Frames: {frame_count}")
                
            except:
                # 队列为空，保持当前显示
                pass
            
            # 继续调度更新（约60fps）
            root.after(16, update_frame)
        
        def on_key_press(event):
            """键盘事件处理"""
            if event.char == 'q' or event.keysym == 'Escape':
                on_closing()
            elif event.char == 's':
                # 保存截图
                try:
                    frame, fps, frame_count = frame_queue.get_nowait()
                    filename = f"screenshot_{int(time.time())}.png"
                    cv2.imwrite(filename, frame)
                    print(f"截图已保存: {filename}")
                    status_label.config(text=f"Saved: {filename}")
                    root.after(2000, lambda: status_label.config(text="Status: Running"))
                except:
                    pass
        
        def on_closing():
            """窗口关闭事件"""
            print("\n用户退出")
            stop_event.set()
            
            # 等待捕获线程结束
            capture_worker.join(timeout=1)
            
            # 显示统计信息
            print("\n" + "=" * 50)
            print("统计信息:")
            print(f"  总帧数: {stats['frame_count']}")
            print(f"  运行时间: {stats['elapsed']:.2f} 秒")
            print(f"  平均FPS: {stats['fps']:.2f}")
            print("=" * 50)
            
            root.quit()
            root.destroy()
        
        # 绑定事件
        root.bind('<KeyPress>', on_key_press)
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
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
