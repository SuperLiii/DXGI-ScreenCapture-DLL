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

# 定义DirtyRect结构体
class DirtyRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int),
        ("top", ctypes.c_int),
        ("right", ctypes.c_int),
        ("bottom", ctypes.c_int)
    ]

class DxgiCapture:
    def __init__(self, dll_path="../DxgiGrab2.dll"):
        """初始化DXGI捕获
        
        Args:
            dll_path: DLL文件路径
        """
        # 加载DLL - 尝试多个可能的路径
        dll_file = Path(dll_path)
        
        if not dll_file.exists():
            # 尝试其他可能的路径
            for possible_path in [
                "DxgiGrab2.dll",
                "../DxgiGrab2.dll",
                "../../DxgiGrab2.dll",
                r"C:\Users\Administrator\Desktop\DXGI-ScreenCapture-DLL\DxgiGrab2.dll"
            ]:
                dll_file = Path(possible_path)
                if dll_file.exists():
                    break
        
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
            print("DXGI实例已销毁")

def capture_thread(capture, frame_queue, stop_event, stats):
    """捕获线程 - 持续捕获屏幕帧（使用脏矩形优化）
    
    Args:
        capture: DxgiCapture实例
        frame_queue: 帧队列
        stop_event: 停止事件
        stats: 统计信息字典
    """
    frame_count = 0
    update_count = 0  # 实际更新的帧数
    start_time = time.time()
    total_dirty_count = 0
    total_dirty_size = 0
    total_full_size = 0
    frames_with_changes = 0
    error_count = 0
    last_valid_frame = None  # 保存上一次有效帧
    
    print("[捕获线程] 开始运行...")
    print("[模式] 只在有变化时更新画面")
    
    # 先获取并跳过第一帧（使用capture方法，因为DXGI第一帧通常是黑的）
    print("[捕获线程] 跳过第一帧...")
    status1, _ = capture.capture(timeout_ms=1000)
    
    # 再获取一个初始帧用于首次显示（使用capture方法，确保能获取到帧）
    print("[捕获线程] 获取初始帧...")
    status2, frame = capture.capture(timeout_ms=1000)
    if status2 == FS_OK and frame is not None:
        last_valid_frame = frame
        # 放入初始帧，脏矩形信息为空（初始化状态）
        try:
            init_dirty = {'count': 0, 'rects': [], 'size': 0, 'saved_percent': 0.0}
            frame_queue.put_nowait((frame, 0, 0, init_dirty))
            print("[捕获线程] 初始帧已加载")
        except:
            pass
    
    while not stop_event.is_set():
        try:
            # 使用脏矩形方式捕获
            status, frame, dirty_info = capture.capture_dirty_rects(timeout_ms=16)
            
            if status == FS_OK and dirty_info is not None:
                frame_count += 1
                current_time = time.time()
                
                # 统计脏矩形信息
                if dirty_info['count'] > 0:
                    frames_with_changes += 1
                    total_dirty_count += dirty_info['count']
                    total_dirty_size += dirty_info['size']
                    total_full_size += capture.size
                    
                    # 只在有变化时才有新帧
                    if frame is not None:
                        last_valid_frame = frame
                        update_count += 1
                
                # 计算FPS
                elapsed = current_time - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                
                # 计算平均节省比例
                avg_saved = 0.0
                if total_full_size > 0:
                    avg_saved = (1.0 - total_dirty_size / total_full_size) * 100.0
                
                # 更新统计信息
                stats['fps'] = fps
                stats['frame_count'] = frame_count
                stats['update_count'] = update_count
                stats['elapsed'] = elapsed
                stats['dirty_count'] = dirty_info['count']
                stats['dirty_size'] = dirty_info['size']
                stats['saved_percent'] = dirty_info['saved_percent']
                stats['total_dirty_rects'] = total_dirty_count
                stats['frames_with_changes'] = frames_with_changes
                stats['avg_saved_percent'] = avg_saved
                stats['dirty_rects'] = dirty_info['rects'][:5]  # 只保留前5个用于显示
                
                # 如果有新帧或者队列为空，放入队列
                if frame is not None or frame_queue.empty():
                    # 如果队列满了，移除旧帧
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                        except:
                            pass
                    
                    # 放入新帧或上一帧（没变化时）
                    try:
                        display_frame = frame if frame is not None else last_valid_frame
                        if display_frame is not None:
                            frame_queue.put_nowait((display_frame, fps, frame_count, dirty_info))
                    except:
                        pass
                    
                # 每100帧打印一次状态
                if frame_count % 100 == 0:
                    print(f"[捕获线程] 检测 {frame_count} 帧, 更新 {update_count} 帧, FPS: {fps:.2f}, " +
                          f"变化率: {frames_with_changes/frame_count*100:.1f}%")
                    
            elif status == FS_TIMEOUT:
                # 超时是正常的
                pass
            else:
                error_count += 1
                if error_count == 1:  # 只打印第一次错误
                    print(f"[捕获线程] 捕获错误: status={status}")
                if error_count > 100:  # 连续错误太多，退出
                    print("[捕获线程] 错误过多，退出")
                    break
                    
        except Exception as e:
            print(f"[捕获线程] 异常: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"[捕获线程] 已停止 - 总检测:{frame_count}帧, 实际更新:{update_count}帧")

def main():
    """主函数"""
    print("=" * 60)
    print("DXGI屏幕捕获测试 - 脏矩形优化版本")
    print("使用DxgiGrab2.dll测试脏矩形功能")
    print("按 'q' 或关闭窗口退出, 按 's' 保存截图")
    print("=" * 60)
    
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
        print("提示: 使用增量更新模式 - 只在有变化时更新画面")
        print("提示: 脏矩形会用黄色边框标记")
        print("提示: 拖动窗口时画面会持续更新")
        print("提示: 移动鼠标或打开窗口可产生脏矩形")
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
        
        # 创建信息标签 - 第一行
        info_frame = tk.Frame(root, bg='black')
        info_frame.pack(fill=tk.X)
        
        fps_label = tk.Label(info_frame, text="FPS: 0.00", fg='lime', bg='black', 
                            font=('Arial', 12, 'bold'))
        fps_label.pack(side=tk.LEFT, padx=10)
        
        resolution_label = tk.Label(info_frame, 
                                   text=f"Resolution: {capture.width}x{capture.height}",
                                   fg='white', bg='black', font=('Arial', 10))
        resolution_label.pack(side=tk.LEFT, padx=10)
        
        frames_label = tk.Label(info_frame, text="检测: 0 | 更新: 0", fg='white', bg='black',
                               font=('Arial', 10))
        frames_label.pack(side=tk.LEFT, padx=10)
        
        status_label = tk.Label(info_frame, text="Status: Running", fg='lightgreen',
                               bg='black', font=('Arial', 9))
        status_label.pack(side=tk.LEFT, padx=10)
        
        # 创建信息标签 - 第二行（脏矩形信息）
        dirty_frame = tk.Frame(root, bg='black')
        dirty_frame.pack(fill=tk.X)
        
        dirty_count_label = tk.Label(dirty_frame, text="Dirty Rects: 0", fg='yellow', bg='black',
                                     font=('Arial', 10, 'bold'))
        dirty_count_label.pack(side=tk.LEFT, padx=10)
        
        dirty_size_label = tk.Label(dirty_frame, text="Dirty Size: 0 B", fg='cyan', bg='black',
                                    font=('Arial', 9))
        dirty_size_label.pack(side=tk.LEFT, padx=10)
        
        saved_label = tk.Label(dirty_frame, text="Saved: 0.0%", fg='orange', bg='black',
                              font=('Arial', 10, 'bold'))
        saved_label.pack(side=tk.LEFT, padx=10)
        
        avg_saved_label = tk.Label(dirty_frame, text="Avg Saved: 0.0%", fg='lightblue', bg='black',
                                   font=('Arial', 9))
        avg_saved_label.pack(side=tk.LEFT, padx=10)
        
        photo_image = None
        
        def update_frame():
            """更新帧显示"""
            nonlocal photo_image
            
            if stop_event.is_set():
                return
            
            try:
                # 尝试获取最新帧（包含脏矩形信息）
                frame, fps, frame_count, dirty_info = frame_queue.get_nowait()
                
                if frame is None:
                    print("警告: 帧为None")
                    root.after(16, update_frame)
                    return
                
                # BGR转RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # 在帧上绘制脏矩形边框（可视化）
                if dirty_info and dirty_info['count'] > 0:
                    for rect in dirty_info['rects'][:10]:  # 最多显示10个
                        cv2.rectangle(frame_rgb, 
                                    (rect['left'], rect['top']),
                                    (rect['right'], rect['bottom']),
                                    (255, 255, 0), 2)  # 黄色边框
                
                # 调整大小
                frame_resized = cv2.resize(frame_rgb, (display_width, display_height))
                
                # 转换为PIL Image
                img = Image.fromarray(frame_resized)
                photo_image = ImageTk.PhotoImage(image=img)
                
                # 更新Canvas
                canvas.delete("all")
                canvas.create_image(0, 0, anchor=tk.NW, image=photo_image)
                
                # 更新基本信息标签
                fps_label.config(text=f"FPS: {fps:.2f}")
                
                # 更新帧数显示
                update_count = stats.get('update_count', 0)
                frames_label.config(text=f"检测: {frame_count} | 更新: {update_count}")
                
                # 更新脏矩形信息标签
                if dirty_info:
                    dirty_count_label.config(text=f"Dirty Rects: {dirty_info['count']}")
                    
                    # 格式化大小显示
                    if dirty_info['size'] > 1024 * 1024:
                        size_text = f"Dirty Size: {dirty_info['size']/1024/1024:.2f} MB"
                    elif dirty_info['size'] > 1024:
                        size_text = f"Dirty Size: {dirty_info['size']/1024:.2f} KB"
                    else:
                        size_text = f"Dirty Size: {dirty_info['size']} B"
                    dirty_size_label.config(text=size_text)
                    
                    saved_label.config(text=f"Saved: {dirty_info['saved_percent']:.1f}%")
                    
                    # 更新平均节省比例
                    if 'avg_saved_percent' in stats:
                        avg_saved_label.config(text=f"Avg Saved: {stats['avg_saved_percent']:.1f}%")
                
            except Exception as e:
                # 队列为空或其他错误，保持当前显示
                if str(e) != "":  # 忽略空队列异常
                    print(f"更新帧错误: {e}")
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
                    frame, fps, frame_count, dirty_info = frame_queue.get_nowait()
                    filename = f"screenshot_{int(time.time())}.png"
                    cv2.imwrite(filename, frame)
                    print(f"截图已保存: {filename}")
                    if dirty_info:
                        print(f"  脏矩形数量: {dirty_info['count']}")
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
            print("\n" + "=" * 60)
            print("统计信息:")
            print(f"  检测帧数: {stats.get('frame_count', 0)}")
            print(f"  更新帧数: {stats.get('update_count', 0)} (实际传输)")
            print(f"  跳过帧数: {stats.get('frame_count', 0) - stats.get('update_count', 0)} (无变化)")
            print(f"  运行时间: {stats.get('elapsed', 0):.2f} 秒")
            print(f"  平均FPS: {stats.get('fps', 0):.2f}")
            print("-" * 60)
            print("脏矩形统计:")
            print(f"  有变化的帧数: {stats.get('frames_with_changes', 0)}")
            print(f"  脏矩形总数: {stats.get('total_dirty_rects', 0)}")
            print(f"  平均节省数据量: {stats.get('avg_saved_percent', 0):.1f}%")
            
            # 计算实际节省的数据量
            update_count = stats.get('update_count', 0)
            frame_count = stats.get('frame_count', 0)
            if frame_count > 0:
                # 如果每帧都传输的数据量
                full_size = capture.size * frame_count
                # 实际传输的数据量（只传输有变化的帧）
                actual_size = capture.size * update_count
                saved_mb = (full_size - actual_size) / 1024 / 1024
                saved_percent = (1 - update_count / frame_count) * 100
                print(f"  通过跳帧节省: {saved_mb:.2f} MB ({saved_percent:.1f}%)")
            print("=" * 60)
            
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
