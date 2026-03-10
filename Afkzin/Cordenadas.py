import pyautogui
import time

print("Posicione o mouse e aguarde 3 segundos...")
try:
    while True:
        # Mostra a posição em tempo real
        x, y = pyautogui.position()
        print(f"X: {x} | Y: {y} (Pressione CTRL+C para parar)", end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    print(f"\nCoordenada final capturada: ({x}, {y})")