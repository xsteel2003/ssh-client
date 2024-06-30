import paramiko
import threading
import time
import socket
import select
import random
import socks5p

# 确定随机端口
local_port = random.randint(10000, 19999)
remote_port = random.randint(10000, 19999)

# 硬编码配置
ssh_address = 'mp3.nongli.vip'
ssh_port = 35536
ssh_username = 'usercdma222'
ssh_password = 'cdma222222'

# 初始化连接状态
ssh_client = None
ssh_connected = False

# 启动 SOCKS5 代理服务器的函数
def start_socks5_proxy():
    server = socks5p.Socks5Server('0.0.0.0', local_port)
    server.start()
    return server

# 在独立的线程中启动 SOCKS5 代理服务器
proxy_thread = threading.Thread(target=start_socks5_proxy)
proxy_thread.daemon = True
proxy_thread.start()
time.sleep(2)  # 等待服务器启动

# 处理 SSH 连接的函数
def connect_ssh():
    global ssh_client, ssh_connected
    try:
        # 创建SSH客户端
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接到SSH服务器
        ssh_client.connect(ssh_address, port=ssh_port, username=ssh_username, password=ssh_password)
        ssh_connected = True
        print("SSH 连接成功")

        # 建立反向端口转发
        transport = ssh_client.get_transport()
        local_host = '127.0.0.1'

        def reverse_forward_tunnel(server_port, remote_host, remote_port, transport):
            try:
                transport.request_port_forward('', server_port)
                print(f"开始反向端口转发：本地端口 {server_port} -> 远程 {remote_host}:{remote_port}")

                while ssh_connected:
                    chan = transport.accept(1000)
                    if chan is None:
                        continue

                    thr = threading.Thread(target=handler, args=(chan, remote_host, remote_port))
                    thr.setDaemon(True)
                    thr.start()
            except Exception as e:
                print(f"反向端口转发失败: {e}")

        def handler(chan, host, port):
            sock = socket.socket()
            try:
                sock.connect((host, port))
                print(f"成功连接到 {host}:{port}")
            except Exception as e:
                chan.close()
                print(f"连接到 {host}:{port} 失败: {e}")
                return

            while ssh_connected:
                try:
                    r, w, x = select.select([sock, chan], [], [])
                    if sock in r:
                        data = sock.recv(1024)
                        if len(data) == 0:
                            break
                        chan.send(data)
                    if chan in r:
                        data = chan.recv(1024)
                        if len(data) == 0:
                            break
                        sock.send(data)
                except Exception as e:
                    print(f"在通道和套接字之间转发数据时出错: {e}")
                    break

            chan.close()
            sock.close()
            print(f"关闭通道和套接字 {host}:{port}")

        reverse_thread = threading.Thread(target=reverse_forward_tunnel, args=(remote_port, local_host, local_port, transport))
        reverse_thread.start()

        print("连接成功，已建立连接")
    except paramiko.AuthenticationException:
        print("连接失败: Authentication failed.")
        ssh_connected = False
    except Exception as e:
        print(f"连接失败: {e}")
        ssh_connected = False

# 保持连接的函数
def keep_connection():
    global ssh_connected
    while ssh_connected:
        time.sleep(1)
    print("连接已断开")

# 启动保持连接的线程
keep_connection_thread = threading.Thread(target=keep_connection)
keep_connection_thread.daemon = True
keep_connection_thread.start()

# 启动SSH连接线程
connect_ssh_thread = threading.Thread(target=connect_ssh)
connect_ssh_thread.daemon = True
connect_ssh_thread.start()

# 控制台显示信息
print(f"本地代理端口: {local_port}")
print(f"SSH 远程端口: {remote_port}")
print("连接状态：正在连接...")
