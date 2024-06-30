import socket
import threading
import select
import sys
import logging
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Socks5Server(threading.Thread):
    def __init__(self, host, port, max_connections=1000):
        super().__init__()
        self.host = host
        self.port = port
        self.buffer_size = 8192  # 增加缓冲区大小以提高性能
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.host, self.port))
        self.server.listen(max_connections)
        self.thread_pool = ThreadPoolExecutor(max_workers=100)  # 使用线程池来管理连接

    def run(self):
        logging.info(f'启动SOCKS5服务器在 {self.host}:{self.port}')
        while True:
            try:
                client_socket, client_address = self.server.accept()
                self.thread_pool.submit(self.handle_client, client_socket, client_address)
            except Exception as e:
                logging.error(f"接受连接时出错: {e}")

    def handle_client(self, client_socket, client_address):
        try:
            client_socket.settimeout(30)  # 设置超时以防止连接挂起
            # 与客户端握手
            if not self.socks5_handshake(client_socket):
                return

            # 接收来自客户端的请求
            data = self.receive_data(client_socket)
            if not data:
                return

            mode = data[1]
            if mode != 1:  # 仅支持CONNECT模式
                return

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
                return

            # 创建到目标服务器的连接
            remote_socket = self.connect_to_target(addr_ip, target_port)
            if not remote_socket:
                return

            # 发送连接成功的回应
            reply = b'\x05\x00\x00\x01' + socket.inet_aton(addr_ip) + target_port.to_bytes(2, 'big')
            client_socket.send(reply)

            # 转发数据
            self.exchange_loop(client_socket, remote_socket)

        except Exception as e:
            logging.error(f"处理客户端时出错: {e}")
        finally:
            client_socket.close()

    def socks5_handshake(self, client_socket):
        data = self.receive_data(client_socket)
        if not data:
            return False
        client_socket.send(b'\x05\x00')
        return True

    def receive_data(self, sock, timeout=5):
        sock.settimeout(timeout)
        try:
            return sock.recv(self.buffer_size)
        except socket.timeout:
            return None

    def connect_to_target(self, addr_ip, target_port):
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(10)
        try:
            remote_socket.connect((addr_ip, target_port))
            return remote_socket
        except Exception as e:
            logging.error(f"连接到目标服务器失败: {e}")
            remote_socket.close()
            return None

    def exchange_loop(self, client_socket, remote_socket):
        sockets = [client_socket, remote_socket]
        timeout = 60
        while True:
            try:
                r, _, _ = select.select(sockets, [], [], timeout)
                if not r:
                    logging.info("连接超时")
                    break
                for sock in r:
                    other = remote_socket if sock is client_socket else client_socket
                    data = sock.recv(self.buffer_size)
                    if not data:
                        return
                    other.sendall(data)
            except Exception as e:
                logging.error(f"数据交换时出错: {e}")
                break
        client_socket.close()
        remote_socket.close()

def main(port):
    try:
        server = Socks5Server('0.0.0.0', port)
        server.start()
        server.join()
    except Exception as e:
        logging.error(f"服务器运行时出错: {e}")
    finally:
        logging.info("服务器正在关闭...")

if __name__ == '__main__':
    DEFAULT_PORT = 16677
    
    if len(sys.argv) > 2:
        print("使用方法: python script.py [端口号]")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1]) if len(sys.argv) == 2 else DEFAULT_PORT
        logging.info(f"使用端口: {port}")
        main(port)
    except ValueError:
        logging.error("错误: 端口号必须是一个有效的整数")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("服务器正在关闭...")
        sys.exit(0)