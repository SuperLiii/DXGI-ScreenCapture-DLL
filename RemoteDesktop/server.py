"""
远程桌面 - 被控端服务器
捕获屏幕并通过网络发送
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ctypes
import numpy as np
import time
import threading
import socket
from pathlib import Path
from queue import Queue, Empty
from protocol import Protocol, PKT_INIT, PKT_FRAME, PKT_DIRTY, PKT_SKIP

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
    def __init__(self, dll_path="../DxgiGrab3.dll"):
        """初始化DXGI捕获"""
        # 加载DLL
        dll_file = Path(dll_path)
        
        if not dll_file.exists():
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
                raise FileNotFoundError(f"找不到DLL文件")
        
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
        
        self.dll.dxgi_acquire_frame.restype = ctypes.c_int
        self.dll.dxgi_acquire_frame.argtypes = [ctypes.c_void_p, ctypes.c_int]
        
        self.dll.dxgi_release_frame.restype = None
        self.dll.dxgi_release_frame.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_dirty_rects_count.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_rects_count.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_get_dirty_rects.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_rects.argtypes = [ctypes.c_void_p, ctypes.POINTER(DirtyRect), ctypes.c_int]
        
        self.dll.dxgi_copy_acquired_frame.restype = ctypes.c_int
        self.dll.dxgi_copy_acquired_frame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char)]
        
        self.dll.dxgi_get_dirty_region_size.restype = ctypes.c_int
        self.dll.dxgi_get_dirty_region_size.argtypes = [ctypes.c_void_p]
        
        self.dll.dxgi_copy_dirty_regions.restype = ctypes.c_int
        self.dll.dxgi_copy_dirty_regions.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_int]
        
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
        self.dirty_buffer = (ctypes.c_char * self.size)()  # 脏区域缓冲
        
        # XOR优化：维护上一帧（BGRA格式）
        self.previous_frame = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        
        print(f"[服务器] 屏幕尺寸: {self.width}x{self.height}, 帧大小: {self.size/1024/1024:.2f} MB")
    
    def capture(self, timeout_ms=100):
        """捕获完整帧（BGRA格式）"""
        status = self.dll.dxgi_get_frame(self.dxgi, self.buffer, timeout_ms)
        
        if status == FS_OK:
            frame = np.frombuffer(self.buffer, dtype=np.uint8).copy()
            frame = frame.reshape(self.height, self.width, 4)  # 保持BGRA格式
            return status, frame
        
        return status, None
    
    def capture_dirty_rects(self, timeout_ms=100):
        """使用脏矩形捕获"""
        status = self.dll.dxgi_acquire_frame(self.dxgi, timeout_ms)
        
        if status != FS_OK:
            return status, None, None
        
        try:
            dirty_count = self.dll.dxgi_get_dirty_rects_count(self.dxgi)
            
            dirty_info = {
                'count': dirty_count,
                'rects': []
            }
            
            # 无变化
            if dirty_count == 0:
                self.dll.dxgi_release_frame(self.dxgi)
                return FS_OK, None, dirty_info
            
            # 获取脏矩形
            rects_array = (DirtyRect * dirty_count)()
            self.dll.dxgi_get_dirty_rects(self.dxgi, rects_array, dirty_count)
            
            dirty_info['rects'] = [
                {
                    'left': r.left,
                    'top': r.top,
                    'right': r.right,
                    'bottom': r.bottom
                }
                for r in rects_array
            ]
            
            # 获取完整帧
            status_frame = self.dll.dxgi_copy_acquired_frame(self.dxgi, self.buffer)
            
            if status_frame == FS_OK:
                frame = np.frombuffer(self.buffer, dtype=np.uint8).copy()
                frame = frame.reshape(self.height, self.width, 4)
                frame = frame[:, :, :3]
                return FS_OK, frame, dirty_info
            
        finally:
            self.dll.dxgi_release_frame(self.dxgi)
        
        return FS_ERROR, None, None
    
    def __del__(self):
        """释放资源"""
        if hasattr(self, 'dxgi') and self.dxgi:
            self.dll.dxgi_destroy(self.dxgi)


class RemoteDesktopServer:
    """远程桌面服务器"""
    
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.capture = None
        self.client_socket = None
        self.running = False
        self.capture_lock = threading.Lock()  # 同步对capture的访问
        
        # 统计信息
        self.stats = {
            'detect_count': 0,
            'send_count': 0,
            'skip_count': 0,
            'bytes_sent': 0,
            'start_time': 0,
            'xor_saved': 0,  # XOR节省的字节数
            'original_size': 0  # 原始未XOR大小
        }
    
    def start(self):
        """启动服务器"""
        try:
            # 初始化捕获
            self.capture = DxgiCapture()
            
            # 创建服务器socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # 禁用Nagle
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB发送缓冲
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)  # 允许多个待处理连接
            
            print(f"[服务器] 监听 {self.host}:{self.port}")
            
            while True:
                print("[服务器] 等待客户端连接...")
                client_socket, client_address = server_socket.accept()
                print(f"[服务器] 客户端已连接: {client_address}")
                
                # 为每个客户端启动新线程
                client_thread = threading.Thread(target=self.handle_client_thread, args=(client_socket, client_address))
                client_thread.daemon = True
                client_thread.start()
        
        except KeyboardInterrupt:
            print("\n[服务器] 正在关闭...")
        except Exception as e:
            print(f"[服务器] 错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            server_socket.close()
    
    def handle_client_thread(self, client_socket, client_address):
        """处理客户端连接的线程函数"""
        try:
            self.client_socket = client_socket
            self.handle_client()
        except Exception as e:
            print(f"[服务器] 客户端 {client_address} 错误: {e}")
        finally:
            if self.client_socket:
                self.client_socket.close()
            print(f"[服务器] 客户端 {client_address} 已断开")
    
    def handle_client(self):
        """处理客户端连接"""
        try:
            # 为每个客户端创建自己的previous_frame副本
            self.previous_frame = self.capture.previous_frame.copy()
            
            # 发送初始化信息
            init_packet = Protocol.pack_init(self.capture.width, self.capture.height)
            Protocol.send_packet(self.client_socket, init_packet)
            print(f"[服务器] 已发送初始化信息")
            
            # 发送首帧
            print("[服务器] 捕获首帧...")
            with self.capture_lock:
                self.capture.capture(timeout_ms=1000)  # 跳过黑屏
                status, frame = self.capture.capture(timeout_ms=1000)
            
            if status == FS_OK and frame is not None:
                frame_bytes = frame.tobytes()
                frame_packet = Protocol.pack_frame(frame_bytes, compress=True)
                Protocol.send_packet(self.client_socket, frame_packet)
                self.stats['send_count'] += 1
                self.stats['bytes_sent'] += len(frame_packet)
                print(f"[服务器] 已发送首帧 ({len(frame_packet)/1024:.1f} KB)")
                
                # 初始化客户端的previous_frame
                self.previous_frame[:] = frame
            
            # 重置统计
            self.stats['detect_count'] = 0
            self.stats['send_count'] = 0
            self.stats['skip_count'] = 0
            self.stats['bytes_sent'] = 0
            self.stats['start_time'] = time.time()
            
            # 持续发送帧
            self.running = True
            print("[服务器] 开始传输屏幕...")
            
            # 启动统计线程
            stats_thread = threading.Thread(target=self.print_stats, daemon=True)
            stats_thread.start()
            
            while self.running:
                try:
                    with self.capture_lock:
                        # 直接控制 DXGI API 流程
                        status = self.capture.dll.dxgi_acquire_frame(self.capture.dxgi, 16)
                        self.stats['detect_count'] += 1
                        
                        if status == FS_OK:
                            try:
                                # 获取脏矩形数量
                                dirty_count = self.capture.dll.dxgi_get_dirty_rects_count(self.capture.dxgi)
                                
                                if dirty_count == 0:
                                    # 无变化，发送跳帧包
                                    skip_packet = Protocol.pack_skip()
                                    Protocol.send_packet(self.client_socket, skip_packet)
                                    self.stats['skip_count'] += 1
                                    self.stats['bytes_sent'] += len(skip_packet)
                                else:
                                    # 有变化，获取脏矩形坐标
                                    rects_array = (DirtyRect * dirty_count)()
                                    self.capture.dll.dxgi_get_dirty_rects(self.capture.dxgi, rects_array, dirty_count)
                                    
                                    rects = [
                                        {
                                            'left': r.left,
                                            'top': r.top,
                                            'right': r.right,
                                            'bottom': r.bottom
                                        }
                                        for r in rects_array
                                    ]
                                    
                                    # 获取脏区域大小并复制数据
                                    dirty_size = self.capture.dll.dxgi_get_dirty_region_size(self.capture.dxgi)
                                    
                                    if dirty_size > 0:
                                        status_dirty = self.capture.dll.dxgi_copy_dirty_regions(
                                            self.capture.dxgi, 
                                            self.capture.dirty_buffer, 
                                            dirty_size
                                        )
                                        
                                        if status_dirty == FS_OK:
                                            # XOR优化：对脏区域进行异或操作
                                            dirty_data = bytes(self.capture.dirty_buffer[:dirty_size])
                                            dirty_array = np.frombuffer(dirty_data, dtype=np.uint8).copy()
                                            
                                            # 处理每个脏矩形区域
                                            offset = 0
                                            xor_array = np.zeros_like(dirty_array)
                                            
                                            for rect in rects:
                                                left, top = rect['left'], rect['top']
                                                width = rect['right'] - rect['left']
                                                height = rect['bottom'] - rect['top']
                                                region_size = width * height * 4  # BGRA
                                                
                                                if offset + region_size <= len(dirty_array):
                                                    # 当前脏区域数据
                                                    current_region = dirty_array[offset:offset+region_size]
                                                    current_region_2d = current_region.reshape(height, width, 4)
                                                    
                                                    # 上一帧对应区域
                                                    previous_region = self.previous_frame[top:top+height, left:left+width]
                                                    
                                                    # XOR操作
                                                    xor_region = np.bitwise_xor(current_region_2d, previous_region)
                                                    xor_array[offset:offset+region_size] = xor_region.flatten()
                                                    
                                                    # 更新previous_frame
                                                    self.previous_frame[top:top+height, left:left+width] = current_region_2d
                                                    
                                                    offset += region_size
                                            
                                            # 统计XOR效果
                                            self.stats['original_size'] += dirty_size
                                            
                                            # 发送XOR后的数据
                                            xor_data = xor_array.tobytes()
                                            dirty_packet = Protocol.pack_dirty(rects, xor_data, compress=True)
                                            
                                            self.stats['xor_saved'] += (dirty_size - len(dirty_packet))
                                            
                                            Protocol.send_packet(self.client_socket, dirty_packet)
                                            self.stats['send_count'] += 1
                                            self.stats['bytes_sent'] += len(dirty_packet)
                                
                            finally:
                                # 释放帧
                                self.capture.dll.dxgi_release_frame(self.capture.dxgi)
                        
                        # 限制频率 60fps
                        time.sleep(0.016)
                    
                except ConnectionResetError:
                    print("[服务器] 客户端断开连接")
                    break
                except BrokenPipeError:
                    print("[服务器] 管道断开")
                    break
                except Exception as e:
                    print(f"[服务器] 传输错误: {e}")
                    break
        
        except Exception as e:
            print(f"[服务器] 客户端处理错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False
            if self.client_socket:
                self.client_socket.close()
    
    def print_stats(self):
        """打印统计信息"""
        print("[统计] 统计线程已启动")
        last_detect = 0
        last_send = 0
        last_skip = 0
        last_bytes = 0
        last_xor_saved = 0
        last_original = 0
        
        while self.running:
            time.sleep(1)
            
            # 计算增量
            detect_delta = self.stats['detect_count'] - last_detect
            send_delta = self.stats['send_count'] - last_send
            skip_delta = self.stats['skip_count'] - last_skip
            bytes_delta = self.stats['bytes_sent'] - last_bytes
            xor_saved_delta = self.stats['xor_saved'] - last_xor_saved
            original_delta = self.stats['original_size'] - last_original
            
            last_detect = self.stats['detect_count']
            last_send = self.stats['send_count']
            last_skip = self.stats['skip_count']
            last_bytes = self.stats['bytes_sent']
            last_xor_saved = self.stats['xor_saved']
            last_original = self.stats['original_size']
            
            total = detect_delta
            bandwidth = bytes_delta / 1024  # KB/s
            skip_percent = (skip_delta / max(1, total)) * 100
            
            # 计算XOR压缩率
            if original_delta > 0:
                compression_ratio = (xor_saved_delta / original_delta) * 100
                print(f"[统计] 检测: {detect_delta}fps | 发送: {send_delta}fps | "
                      f"带宽: {bandwidth:.2f}KB/s | 跳帧: {skip_percent:.1f}% | "
                      f"XOR压缩: {compression_ratio:.1f}%")
            else:
                print(f"[统计] 检测: {detect_delta}fps | 发送: {send_delta}fps | "
                      f"带宽: {bandwidth:.2f}KB/s | 跳帧: {skip_percent:.1f}%")


if __name__ == "__main__":
    server = RemoteDesktopServer(host='0.0.0.0', port=9999)
    server.start()
