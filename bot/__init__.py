import os

dir_path = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(dir_path)
data_dir = os.path.join(parent_dir, 'data')

if not os.path.exists(data_dir):
    os.mkdir(data_dir)