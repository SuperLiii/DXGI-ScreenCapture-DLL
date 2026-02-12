"""
远程桌面Web服务器 - 通过浏览器查看屏幕
支持局域网手机/平板访问
使用MJPEG流，无需额外插件
连接到RemoteDesktop服务器，使用XOR优化的低带宽传输
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import time
import cv2
from flask import Flask, Response, render_template_string
import socket as sock
import threading

# 导入协议
from protocol import Protocol, PKT_FRAME, PKT_DIRTY, PKT_SKIP

app = Flask(__name__)

# 全局状态
tcp_socket = None
frame_buffer = None
current_jpeg = None
jpeg_lock = threading.Lock()
width = 0
height = 0
running = False

# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>远程桌面 - {{ host_ip }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: #1a1a1a;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            overflow: hidden;
        }
        .header {
            background: #2d2d2d;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .header h1 {
            font-size: 18px;
            font-weight: 500;
        }
        .info {
            font-size: 12px;
            color: #888;
        }
        .container {
            width: 100vw;
            height: calc(100vh - 50px);
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px;
        }
        .screen {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            border-radius: 4px;
        }
        @media (max-width: 768px) {
            .header h1 { font-size: 16px; }
            .info { font-size: 11px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🖥️ 远程桌面</h1>
        <div class="info">{{ screen_size }} | {{ host_ip }}</div>
    </div>
    <div class="container">
        <img src="/video_feed" class="screen" alt="Remote Desktop">
    </div>
</body>
</html>
"""

def get_local_ip():
    """获取本机局域网IP"""
    try:
        s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def connect_to_server(server_host='127.0.0.1', server_port=9999):
    """连接到RemoteDesktop服务器"""
    global tcp_socket, frame_buffer, width, height
    
    try:
        print(f"[Web] 连接到服务器 {server_host}:{server_port}...", flush=True)
        tcp_socket = sock.socket(sock.AF_INET, sock.SOCK_STREAM)
        tcp_socket.setsockopt(sock.IPPROTO_TCP, sock.TCP_NODELAY, 1)
        tcp_socket.setsockopt(sock.SOL_SOCKET, sock.SO_RCVBUF, 1048576)
        tcp_socket.connect((server_host, server_port))
        print(f"[Web] 已连接", flush=True)
        
        # 接收初始化信息
        init_packet = Protocol.recv_packet(tcp_socket)
        if not init_packet:
            raise Exception("未收到初始化数据")
        
        width, height = Protocol.unpack_init(init_packet)
        print(f"[Web] 屏幕尺寸: {width}x{height}", flush=True)
        
        # 创建帧缓冲（BGRA格式）
        frame_buffer = np.zeros((height, width, 4), dtype=np.uint8)
        
        # 初始化current_jpeg为空图像
        bgr = frame_buffer[:, :, :3]
        ret, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if ret:
            with jpeg_lock:
                current_jpeg = buffer.tobytes()
        
        return True
        
    except Exception as e:
        print(f"[Web] 连接失败: {e}", flush=True)
        return False

def receive_loop():
    """接收数据循环（后台线程）"""
    global tcp_socket, frame_buffer, current_jpeg, jpeg_lock, running
    
    print("[Web] 接收线程已启动", flush=True)
    
    try:
        while running:
            packet = Protocol.recv_packet(tcp_socket)
            if not packet:
                print("[Web] 连接已断开", flush=True)
                break
            
            pkt_type = Protocol.get_packet_type(packet)
            
            if pkt_type == PKT_SKIP:
                # 跳帧，无需更新
                continue
                
            elif pkt_type == PKT_DIRTY:
                # 脏矩形XOR数据
                rects, xor_data = Protocol.unpack_dirty(packet)
                
                xor_array = np.frombuffer(xor_data, dtype=np.uint8)
                offset = 0
                
                for rect in rects:
                    left, top = rect['left'], rect['top']
                    width_r, height_r = rect['width'], rect['height']
                    region_size = width_r * height_r * 4
                    
                    if offset + region_size <= len(xor_array):
                        xor_region_data = xor_array[offset:offset+region_size]
                        xor_region = xor_region_data.reshape(height_r, width_r, 4)
                        
                        # XOR恢复：xor XOR old = new
                        frame_buffer[top:top+height_r, left:left+width_r] = np.bitwise_xor(
                            frame_buffer[top:top+height_r, left:left+width_r],
                            xor_region
                        )
                        offset += region_size
                
                # 编码为JPEG
                bgr = frame_buffer[:, :, :3]
                ret, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    with jpeg_lock:
                        current_jpeg = buffer.tobytes()
            
            elif pkt_type == PKT_FRAME:
                # 完整帧
                frame_data = Protocol.unpack_frame(packet)
                frame = np.frombuffer(frame_data, dtype=np.uint8)
                frame = frame.reshape(height, width, 4)
                frame_buffer[:] = frame
                
                # 编码为JPEG
                bgr = frame[:, :, :3]
                ret, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    with jpeg_lock:
                        current_jpeg = buffer.tobytes()
    
    except Exception as e:
        print(f"[Web] 接收错误: {e}", flush=True)
    finally:
        running = False
        print("[Web] 接收线程已退出", flush=True)

def generate_frames():
    """生成MJPEG帧流"""
    global current_jpeg, jpeg_lock
    
    # 等待第一帧
    while current_jpeg is None and running:
        time.sleep(0.01)
    
    last_jpeg = None
    
    while running:
        with jpeg_lock:
            if current_jpeg is not None and current_jpeg != last_jpeg:
                jpeg_data = current_jpeg
                last_jpeg = current_jpeg
            else:
                jpeg_data = None
        
        if jpeg_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg_data + b'\r\n')
        
        time.sleep(0.05)  # 20fps

@app.route('/')
def index():
    """主页"""
    global width, height
    
    host_ip = get_local_ip()
    screen_size = f"{width}x{height}"
    
    return render_template_string(
        HTML_TEMPLATE, 
        host_ip=host_ip,
        screen_size=screen_size
    )

@app.route('/video_feed')
def video_feed():
    """MJPEG视频流"""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

def start_server():
    """启动服务器主函数"""
    global running
    import sys
    
    print("\n" + "="*60, flush=True)
    print("远程桌面Web服务器 (XOR优化版)", flush=True)
    print("="*60, flush=True)
    
    # 连接到RemoteDesktop服务器
    server_host = '127.0.0.1'  # 如果server.py在同一台机器
    server_port = 9999
    
    if not connect_to_server(server_host, server_port):
        print("\n❌ 无法连接到RemoteDesktop服务器", flush=True)
        print(f"   请确保 server.py 正在运行于 {server_host}:{server_port}", flush=True)
        print("="*60 + "\n", flush=True)
        sys.exit(1)
    
    running = True
    
    # 启动接收线程
    recv_thread = threading.Thread(target=receive_loop, daemon=True)
    recv_thread.start()
    
    host_ip = get_local_ip()
    port = 5000
    
    print(f"\n✅ 服务器启动成功！", flush=True)
    print(f"\n📱 手机访问地址：", flush=True)
    print(f"   http://{host_ip}:{port}", flush=True)
    print(f"\n💻 本机访问地址：", flush=True)
    print(f"   http://127.0.0.1:{port}", flush=True)
    print(f"\n💡 特性：XOR优化低带宽传输", flush=True)
    print(f"   提示：确保手机和电脑在同一局域网", flush=True)
    print("="*60 + "\n", flush=True)
    
    sys.stdout.flush()
    
    try:
        # 启动Flask服务器
        app.run(
            host='0.0.0.0',  # 监听所有网卡
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False  # 禁用重载避免双重启动
        )
    finally:
        running = False
        if tcp_socket:
            tcp_socket.close()

if __name__ == '__main__':
    start_server()
