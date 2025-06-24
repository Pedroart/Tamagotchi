import torch
print(torch.cuda.is_available())  # True si CUDA está disponible
print(torch.cuda.current_device())  # Te da el índice actual
print(torch.cuda.get_device_name(0))  # Nombre de tu GPU
import torchaudio
print("torchaudio version:", torchaudio.__version__)
