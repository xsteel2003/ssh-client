import socket
import threading
import select
import sys

class Socks5Server(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self.host = host
        self.port = port
        self.buffer_size = 4096  # 设置数据缓冲大小
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(5)

    def run(self):
        print(f'启动SOCKS5服务器在 {self.host}:{self.port}')
        while True:
            client_socket, client_address = self.server.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
            client_thread.start()

    def handle_client(self, client_socket, client_address):
        try:
            # 与客户端握手
            client_socket.recv(self.buffer_size)  # 接收客户端的握手数据
            # 发送握手响应，无需验证
            client_socket.send(b'\x05\x00')
            # 接收来自客户端的请求
            data = client_socket.recv(self.buffer_size)
            mode = data[1]
            if mode == 1:  # CONNECT
                addr_type = data[3]
                if addr_type == 1:  # IPv4
                    addr_ip = socket.inet_ntoa(data[4:8])
                    target_port = int.from_bytes(data[8:10], 'big')
                elif addr_type == 3:  # 域名
                    addr_len = data[4]
                    addr_domain = data[5:5+addr_len].decode('utf-8')
                    target_port = int.from_bytes(data[5+addr_len:7+addr_len], 'big')
                    addr_ip = socket.gethostbyname(addr_domain)
                else:
                    client_socket.close()
                    return

                # 创建到目标服务器的连接
                remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    remote_socket.connect((addr_ip, target_port))
                    # 发送连接成功的回应
                    reply = b'\x05\x00\x00\x01'
                    reply += socket.inet_aton(addr_ip) + target_port.to_bytes(2, 'big')
                    client_socket.send(reply)
                except Exception as e:
                    print(f"连接到目标服务器失败: {e}")
                    client_socket.close()
                    return

                # 转发数据
                self.exchange_loop(client_socket, remote_socket)
            else:
                client_socket.close()
        except Exception as e:
            print(f"处理客户端时出错: {e}")
            client_socket.close()

    def exchange_loop(self, client_socket, remote_socket):
        sockets = [client_socket, remote_socket]
        try:
            while True:
                # 等待数据
                r, w, e = select.select(sockets, [], [], 60)
                if not r:
                    continue
                for sock in r:
                    other = remote_socket if sock is client_socket else client_socket
                    data = sock.recv(self.buffer_size)
                    if not data:
                        return
                    other.send(data)
        finally:
            client_socket.close()
            remote_socket.close()

if __name__ == '__main__':
    DEFAULT_PORT = 16677
    
    if len(sys.argv) > 2:
        print("使用方法: python script.py [端口号]")
        sys.exit(1)
    
    try:
        if len(sys.argv) == 2:
            port = int(sys.argv[1])
        else:
            port = DEFAULT_PORT
        
        print(f"使用端口: {port}")
        server = Socks5Server('0.0.0.0', port)
        server.start()
        server.join()  # 等待服务器线程结束
    except ValueError:
        print("错误: 端口号必须是一个有效的整数")
        sys.exit(1)
    except KeyboardInterrupt:
        print("服务器正在关闭...")
        sys.exit(0)