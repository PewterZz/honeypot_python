import paramiko
import sys
import socket
import threading
import os
import logging
import select
import time

SSH_HOST = '127.0.0.1'  
SSH_PORT = 22  

FAKE_PORTS = [80, 443, 8000]


BANNER = 'SSH-2.0-OpenSSH_7.4'

USERNAME = 'admin'
PASSWORD = 'password'

# Define the SSH server handler
class SSHServerHandler(paramiko.ServerInterface):
    def __init__(self, client_address):
        self.client_address = client_address
        self.authenticated = False

    def log_command(self, command):
        logging.info(f"[{self.client_address}] Command executed: {command}")

    def check_auth_password(self, username, password):
        logging.info(f"[{self.client_address}] Attempted login - Username: {username}, Password: {password}")
        if username == USERNAME and password == PASSWORD:
            self.authenticated = True
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_request(self, kind, chanid):
        print(f"Channel type requested: {kind}")
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def start_shell(self, channel):
        channel.send('Welcome to the custom shell!\n')
        channel.send('$ ')

        shell_channel = channel.invoke_shell()
        self._handle_shell(shell_channel)

        shell_channel.close()
        channel.close()

    def _handle_shell(self, shell_channel):
        while True:
            try:
                if shell_channel.exit_status_ready():
                    break

                if shell_channel.recv_ready():
                    output = shell_channel.recv(1024).decode().strip()
                    sys.stdout.write(output)
                    sys.stdout.flush()

                if shell_channel.send_ready():
                    command = shell_channel.recv(1024).decode().strip()
                    if command:
                        self.log_command(command)
                        if command == 'exit':
                            shell_channel.send('Exiting custom shell.\n')
                            break
                        else:
                            output = self._execute(command)
                            shell_channel.send(output + '$ ')

                if shell_channel.recv_stderr_ready():
                    error_output = shell_channel.recv_stderr(1024).decode().strip()
                    sys.stderr.write(error_output + '\n')
                    sys.stderr.flush()

            except Exception as e:
                print(f"Error handling shell: {str(e)}")
                break

        # Delay before closing the channel and transport
        time.sleep(1)
        shell_channel.close()
        shell_channel.get_transport().close()

    def _execute(self, command):
        if command == 'ls':
            files = os.listdir('.')
            return '\n'.join(files) + '\n'
        elif command.startswith('touch '):
            filename = command.split(' ')[1]
            try:
                open(filename, 'a').close()
                return f"File '{filename}' created.\n"
            except Exception as e:
                return f"Error creating file: {str(e)}\n"
        elif command.startswith('cat '):
            filename = command.split(' ')[1]
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                    return content + '\n'
            except Exception as e:
                return f"Error reading file: {str(e)}\n"
        else:
            return f"Command not found: {command}\n"



# Define the SSH server thread
class SSHServerThread(threading.Thread):
    def __init__(self, client, addr):
        threading.Thread.__init__(self)
        self.client = client
        self.addr = addr

    def run(self):
        transport = paramiko.Transport(self.client)
        transport.add_server_key(paramiko.RSAKey.generate(2048))
        server_handler = SSHServerHandler(self.addr[0])

        transport.set_subsystem_handler("sftp", paramiko.SFTPServer, {})

        transport.start_server(server=server_handler)
        channel = transport.accept(20)
        if channel is None:
            transport.close()
            return

        channel.get_pty = lambda *args: False  # Disable PTY allocation

        server_handler.start_shell(channel)
        channel.close()
        transport.close()

# Main execution
def main():
    # Configure logging
    logging.basicConfig(filename='honeypot.log', level=logging.INFO,
                        format='%(asctime)s - %(message)s')

    # Start SSH honeypot
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SSH_HOST, SSH_PORT))
    server_socket.listen(5)
    print(f'SSH honeypot is listening on {SSH_HOST}:{SSH_PORT}')

    # Start fake services
    fake_sockets = []
    for fake_port in FAKE_PORTS:
        fake_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fake_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        fake_socket.bind((SSH_HOST, fake_port))
        fake_socket.listen(5)
        fake_sockets.append(fake_socket)
        print(f'Fake service listening on {SSH_HOST}:{fake_port}')

    try:
        while True:
            ready_sockets, _, _ = select.select([server_socket] + fake_sockets, [], [])

            for sock in ready_sockets:
                if sock == server_socket:
                    client, addr = server_socket.accept()
                    print(f'Connection from: {addr[0]}:{addr[1]}')
                    t = SSHServerThread(client, addr)
                    t.start()
                else:
                    client, addr = sock.accept()
                    client.close()  # Close the connection to the fake service

    except KeyboardInterrupt:
        print("Shutting down...")
        server_socket.close()
        for sock in fake_sockets:
            sock.close()

if __name__ == '__main__':
    main()
