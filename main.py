import socket
import threading
import subprocess
import os
import tempfile

main_directory = "main"  

def handle_client(client_socket, address):
    print(f"Incoming connection from: {address[0]}:{address[1]}")

    # Send the welcome message
    client_socket.send(b"Welcome to the honeypot!\n")
    print(f"Welcome message sent to {address[0]}:{address[1]}")

    while True:
        try:
            command = client_socket.recv(1024).decode().strip()
        except UnicodeDecodeError:
            command = client_socket.recv(1024)
            print(f"Received raw bytes from {address[0]}:{address[1]}: {command}")
        if not command:
            break

        print(f"Received command from {address[0]}:{address[1]}: {command}")

        with open("honeypot_log.txt", "a") as log_file:
            log_file.write(f"Command from {address[0]}:{address[1]}: {command}\n")

        output = execute_command(command)
        client_socket.send(output.encode())

    client_socket.close()
    print(f"Connection with {address[0]}:{address[1]} closed")

def execute_command(command):
    tokens = command.split()

    if tokens[0] == "touch":
        if len(tokens) > 1:
            filename = os.path.join(main_directory, tokens[1])
            try:
                open(filename, 'a').close()
                return "File created: " + filename
            except Exception as e:
                return f"Error creating file: {str(e)}"
        else:
            return "Please provide a filename."

    elif tokens[0] == "ls":
        try:
            files = os.listdir(main_directory)
            file_list = "\n".join(files)
            return file_list
        except FileNotFoundError:
            return f"Directory not found: {main_directory}"
        except Exception as e:
            return f"Error listing files: {str(e)}"

    elif tokens[0] == "cat":
        if len(tokens) > 1:
            filename = os.path.join(main_directory, tokens[1])
            try:
                with open(filename, 'r') as file:
                    contents = file.read()
                    return contents
            except FileNotFoundError:
                return f"File not found: {filename}"
            except Exception as e:
                return f"Error reading file: {str(e)}"
        else:
            return "Please provide a filename."

    elif tokens[0] == "mkdir":
        if len(tokens) > 1:
            directory = os.path.join(main_directory, tokens[1])
            try:
                os.mkdir(directory)
                return "Directory created: " + directory
            except Exception as e:
                return f"Error creating directory: {str(e)}"
        else:
            return "Please provide a directory name."

    else:
        # Invalid command
        return "Invalid command. Available commands: touch, ls, cat, mkdir"

def start_honeypot(ip, ports):
    if not os.path.exists(main_directory):
        os.mkdir(main_directory)

    threads = []
    for port in ports:
        honeypot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            honeypot_socket.bind((ip, port))

            honeypot_socket.listen(1)
            print(f"Honeypot started on {ip}:{port}")

            thread = threading.Thread(target=accept_connections, args=(honeypot_socket,))
            thread.start()
            threads.append(thread)

        except OSError as e:
            print(f"Error starting honeypot on port {port}: {e}")
        except KeyboardInterrupt:
            break

    for thread in threads:
        thread.join()

def accept_connections(socket):
    while True:
        client_socket, address = socket.accept()

        # Start a new thread to handle the client
        client_thread = threading.Thread(target=handle_client, args=(client_socket, address))
        client_thread.start()

honeypot_ip = "127.0.0.1"
honeypot_ports = [22, 80, 443, 3389]  # Example list of fake ports

start_honeypot(honeypot_ip, honeypot_ports)
