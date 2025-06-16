import os
from .utils.find_port import find_port

dir_path = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(dir_path)
data_dir = os.path.join(parent_dir, "data")
PYRO_HOST = "127.0.0.1"
PYRO_PORT = find_port()

if not os.path.exists(data_dir):
    os.mkdir(data_dir)
