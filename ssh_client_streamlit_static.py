import paramiko
import threading
import time
import socket
import select
import socks5p

class SSHConnection:
    def __init__(self):
        self.ssh_client = None
        self.connected = False
        self.local_port = 16877
        self.remote_port = 16977
        self.ssh_address = 'mp3.nongli.vip'
        self.ssh_port = 35536
        self.ssh_username = 'usercdma222'
        self.ssh_password = 'cdma222222'
        self.reconnect_interval = 10

    def start_socks5_proxy(self):
        server = socks5p.Socks5Server('0.0.0.0', self.local_port)
        server.start()
        return server

    def reverse_forward_tunnel(self, server_port, remote_host, remote_port, transport):
        try:
            transport.request_port_forward('', server_port)
            print(f"开始反向端口转发：服务器本地端口 {server_port} -> 远程 {remote_host}:{remote_port}")

            while self.connected:
                chan = transport.accept(1000)
                if chan is None:
                    continue

                thr = threading.Thread(target=self.handler, args=(chan, remote_host, remote_port))
                thr.setDaemon(True)
                thr.start()
        except Exception as e:
            print(f"反向端口转发失败: {e}")
            self.connected = False

    def handler(self, chan, host, port):
        sock = socket.socket()
        try:
            sock.connect((host, port))
            print(f"成功连接到 {host}:{port}")
        except Exception as e:
            chan.close()
            print(f"连接到 {host}:{port} 失败: {e}")
            return

        while self.connected:
            try:
                r, w, x = select.select([sock, chan], [], [], 1)
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

    def connect_ssh(self):
        while True:
            try:
                if self.connected:
                    time.sleep(5)  # 如果已连接，每5秒检查一次
                    continue

                # 创建SSH客户端
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                # 连接到SSH服务器
                self.ssh_client.connect(self.ssh_address, port=self.ssh_port, username=self.ssh_username, password=self.ssh_password)
                self.connected = True
                print("SSH 连接成功")

                # 建立反向端口转发
                transport = self.ssh_client.get_transport()
                local_host = '127.0.0.1'

                reverse_thread = threading.Thread(target=self.reverse_forward_tunnel, args=(self.remote_port, local_host, self.local_port, transport))
                reverse_thread.start()

                print("连接成功，已建立连接")

                # 保持连接
                while self.connected:
                    time.sleep(5)
                    try:
                        self.ssh_client.exec_command('echo keepalive', timeout=10)
                    except Exception as e:
                        print(f"保持连接失败: {e}")
                        self.connected = False
                        break

            except paramiko.AuthenticationException:
                print("连接失败: Authentication failed.")
                self.connected = False
            except Exception as e:
                print(f"连接失败: {e}")
                self.connected = False

            if not self.connected:
                print(f"连接断开，{self.reconnect_interval}秒后尝试重新连接...")
                if self.ssh_client:
                    self.ssh_client.close()
                time.sleep(self.reconnect_interval)

    def run(self):
        # 启动 SOCKS5 代理服务器
        proxy_thread = threading.Thread(target=self.start_socks5_proxy)
        proxy_thread.daemon = True
        proxy_thread.start()
        time.sleep(2)  # 等待服务器启动

        # 启动SSH连接线程
        connect_ssh_thread = threading.Thread(target=self.connect_ssh)
        connect_ssh_thread.daemon = True
        connect_ssh_thread.start()

        # 控制台显示信息
        print(f"本地代理端口: {self.local_port}")
        print(f"SSH 远程端口: {self.remote_port}")
        print("连接状态：正在连接...")

        # 保持主线程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("程序正在退出...")
            self.connected = False
            if self.ssh_client:
                self.ssh_client.close()

if __name__ == "__main__":
    ssh_connection = SSHConnection()
    ssh_connection.run()
