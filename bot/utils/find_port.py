import socket

start_port = 8001
max_attempts = 15
host = "127.0.0.1"


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_port() -> int:
    current_port = start_port
    print("Ищем свободный порт для Pyrogram...")
    for _ in range(max_attempts):
        if is_port_available(host, current_port):
            print(f"Найден свободный порт: {current_port}")
            return current_port
        current_port += 1
    raise RuntimeError(
        f"Не нашлось свободных портов в диапазоне: {start_port}-{start_port + max_attempts}"
    )
