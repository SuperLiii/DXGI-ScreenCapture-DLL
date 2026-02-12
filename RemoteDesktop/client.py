"""
远程桌面 - 控制端客户端
接收屏幕数据并显示
"""

import socket
import threading
import time
import numpy as np
import cv2
import tkinter as tk
from PIL import Image, ImageTk
from queue import Queue, Empty
from protocol import Protocol, PKT_INIT, PKT_FRAME, PKT_DIRTY, PKT_SKIP


class RemoteDesktopClient:
    """远程桌面客户端"""
    
    def __init__(self, server_host='127.0.0.1', server_port=9999):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = None
        self.running = False
        
        # 屏幕信息
        self.width = 0
        self.height = 0
        self.current_frame = None
        self.frame_buffer = None  # 完整帧缓冲
        
        # 帧队列（增大以应对突发）
        self.frame_queue = Queue(maxsize=5)
        
        # 统计信息
        self.stats = {
            'recv_count': 0,
            'skip_count': 0,
            'bytes_recv': 0,
            'start_time': 0,
            'last_fps_time': 0,
            'fps_counter': 0,
            'current_fps': 0
        }
    
    def connect(self):
        """连接到服务器"""
        try:
            print(f"[客户端] 连接到 {self.server_host}:{self.server_port}...")
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 优化网络性能
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # 禁用Nagle
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB接收缓冲
            self.socket.connect((self.server_host, self.server_port))
            print(f"[客户端] 已连接")
            
            # 接收初始化信息
            init_packet = Protocol.recv_packet(self.socket)
            if not init_packet:
                raise Exception("未收到初始化数据")
            
            self.width, self.height = Protocol.unpack_init(init_packet)
            print(f"[客户端] 屏幕尺寸: {self.width}x{self.height}")
            
            # 创建帧缓冲（BGRA格式，4通道）
            self.frame_buffer = np.zeros((self.height, self.width, 4), dtype=np.uint8)
            
            # 接收首帧
            first_packet = Protocol.recv_packet(self.socket)
            if not first_packet:
                raise Exception("未收到首帧")
            
            pkt_type = Protocol.get_packet_type(first_packet)
            if pkt_type == PKT_FRAME:
                frame_data = Protocol.unpack_frame(first_packet)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape(self.height, self.width, 4)  # BGRA格式
                self.frame_buffer[:] = frame  # 初始化帧缓冲
                # 直接取BGR通道（前3个通道）
                self.current_frame = frame[:, :, :3].copy()
                print(f"[客户端] 已接收首帧")
            
            self.running = True
            self.stats['start_time'] = time.time()
            self.stats['last_fps_time'] = time.time()
            
            return True
            
        except Exception as e:
            print(f"[客户端] 连接失败: {e}")
            return False
    
    def receive_loop(self):
        """接收数据循环"""
        try:
            while self.running:
                # 接收数据包
                packet = Protocol.recv_packet(self.socket)
                if not packet:
                    print("[客户端] 连接已断开")
                    break
                
                self.stats['bytes_recv'] += len(packet)
                pkt_type = Protocol.get_packet_type(packet)
                
                if pkt_type == PKT_SKIP:
                    # 跳帧包
                    self.stats['skip_count'] += 1
                    
                elif pkt_type == PKT_DIRTY:
                    # 脏矩形局部更新（XOR编码）
                    rects, dirty_data = Protocol.unpack_dirty(packet)
                    
                    # 将脏区域XOR数据应用到帧缓冲
                    dirty_array = np.frombuffer(dirty_data, dtype=np.uint8)
                    offset = 0
                    
                    for rect in rects:
                        left, top = rect['left'], rect['top']
                        width, height = rect['width'], rect['height']
                        region_size = width * height * 4  # BGRA格式，4字节/像素
                        
                        if offset + region_size <= len(dirty_array):
                            # XOR编码的数据
                            xor_data = dirty_array[offset:offset+region_size]
                            xor_region = xor_data.reshape(height, width, 4)  # BGRA格式
                            
                            # XOR恢复：xor_region XOR frame_buffer = 新像素
                            # （服务器：new XOR old = xor，客户端：xor XOR old = new）
                            self.frame_buffer[top:top+height, left:left+width] = np.bitwise_xor(
                                self.frame_buffer[top:top+height, left:left+width], 
                                xor_region
                            )
                            offset += region_size
                    
                    # 直接取BGR通道（前3个通道）
                    self.current_frame = self.frame_buffer[:, :, :3].copy()
                    self.stats['recv_count'] += 1
                    
                    # 放入队列
                    try:
                        # 如果队列满，清空旧帧
                        while self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except:
                                break
                        self.frame_queue.put_nowait(self.current_frame.copy())
                    except:
                        pass
                    
                    # 更新FPS
                    self.stats['fps_counter'] += 1
                    current_time = time.time()
                    if current_time - self.stats['last_fps_time'] >= 1.0:
                        self.stats['current_fps'] = self.stats['fps_counter']
                        self.stats['fps_counter'] = 0
                        self.stats['last_fps_time'] = current_time
                
                elif pkt_type == PKT_FRAME:
                    # 完整帧
                    frame_data = Protocol.unpack_frame(packet)
                    frame = np.frombuffer(frame_data, dtype=np.uint8)
                    frame = frame.reshape(self.height, self.width, 4)  # BGRA格式
                    
                    # 直接取BGR通道（前3个通道）
                    self.current_frame = frame[:, :, :3].copy()
                    self.stats['recv_count'] += 1
                    
                    if self.frame_queue.full():
                        try:
                            self.frame_queue.get_nowait()
                        except:
                            pass
                    try:
                        self.frame_queue.put_nowait(self.current_frame.copy())
                    except:
                        pass
        
        except ConnectionResetError:
            print("[客户端] 连接被重置")
        except Exception as e:
            print(f"[客户端] 接收错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
    
    def start_gui(self):
        """启动GUI显示"""
        # 创建窗口
        root = tk.Tk()
        root.title(f"远程桌面 - {self.server_host}:{self.server_port}")
        
        # 计算显示尺寸
        display_width = 1280
        display_height = int(display_width * self.height / self.width)
        
        # 创建Canvas
        canvas = tk.Canvas(root, width=display_width, height=display_height, bg='black')
        canvas.pack()
        
        # 创建状态标签
        status_label = tk.Label(root, text="", font=("Arial", 10))
        status_label.pack()
        
        photo_image = None
        last_frame_id = None
        
        def update_frame():
            """更新帧显示"""
            nonlocal photo_image, last_frame_id
            
            if not self.running:
                root.quit()
                return
            
            has_new_frame = False
            
            try:
                frame = self.frame_queue.get_nowait()
                
                if frame is not None:
                    frame_id = id(frame)
                    
                    if frame_id != last_frame_id:
                        last_frame_id = frame_id
                        has_new_frame = True
                        
                        # BGR转RGB
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        
                        # 调整大小（使用快速插值）
                        frame_resized = cv2.resize(frame_rgb, (display_width, display_height), 
                                                  interpolation=cv2.INTER_LINEAR)
                        
                        # 转换为PIL Image
                        img = Image.fromarray(frame_resized)
                        photo_image = ImageTk.PhotoImage(image=img)
                        
                        # 更新Canvas
                        canvas.delete("all")
                        canvas.create_image(0, 0, anchor=tk.NW, image=photo_image)
            except Empty:
                pass
            except Exception as e:
                pass  # 忽略偶发错误，保持运行
            
            # 更新状态
            elapsed = time.time() - self.stats['start_time']
            if elapsed > 0:
                bandwidth = self.stats['bytes_recv'] / elapsed / 1024 / 1024  # MB/s
                status_text = f"FPS: {self.stats['current_fps']} | 带宽: {bandwidth:.2f} MB/s | 接收: {self.stats['recv_count']} | 跳帧: {self.stats['skip_count']}"
                status_label.config(text=status_text)
            
            # 动态刷新间隔（提高刷新频率）
            next_interval = 16 if has_new_frame else 50
            root.after(next_interval, update_frame)
        
        def on_closing():
            """窗口关闭"""
            self.running = False
            if self.socket:
                self.socket.close()
            root.quit()
            root.destroy()
        
        def on_key_press(event):
            """键盘事件"""
            if event.char == 'q' or event.keysym == 'Escape':
                on_closing()
            elif event.char == 's':
                # 保存截图
                if self.current_frame is not None:
                    filename = f"remote_screenshot_{int(time.time())}.png"
                    cv2.imwrite(filename, self.current_frame)
                    print(f"[客户端] 截图已保存: {filename}")
        
        # 绑定事件
        root.bind('<KeyPress>', on_key_press)
        root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # 启动更新
        root.after(100, update_frame)
        
        # 主循环
        root.mainloop()
    
    def run(self):
        """运行客户端"""
        if not self.connect():
            return
        
        # 启动接收线程
        recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        recv_thread.start()
        
        # 启动GUI
        self.start_gui()
        
        print("[客户端] 已退出")


if __name__ == "__main__":
    import sys
    
    # 命令行参数: python client.py [host] [port]
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    
    client = RemoteDesktopClient(server_host=host, server_port=port)
    client.run()
