import tkinter as tk
import json
import os
import pydirectinput
import time
import mss
import numpy as np
import cv2
import keyboard
import pyautogui
import ctypes

# --- CONFIGURAÇÕES DE USUÁRIO ---
SCREEN_W, SCREEN_H = 1920, 1080
CONFIG_FILE = "config_bot.json"
TEMPO_AFK = 60          # Segundos entre ciclos
TEMPO_COOLDOWN = 900    # Segundos de pausa (15 minutos)
CONFIANCA_BUSCA = 0.2   # Sensibilidade do reconhecimento de imagem

# Atalhos
STOP_KEY = 'end' 
CONFIG_KEY = 'f2'
FORCAR_KEY = 'f4'

# --- PROTEÇÃO E INICIALIZAÇÃO ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()

pydirectinput.FAILSAFE = False
pyautogui.useImageNotFoundException(False)

# Offsets para botões específicos que não clicam no centro
OFFSETS_ESPECIFICOS = {
    "compra_p3_3.png": (60, 0),
    "compra_p4_3.png": (60, 0)
}

# --- NÚCLEO DE VISÃO ---

def localizar_escala_dinamica(img_path):
    if not os.path.exists(img_path): return None
    template = cv2.imread(img_path, 0)
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        screen_gray = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2GRAY)

    melhor_val, melhor_loc, dim_vencedora = -1, None, (0, 0)
    for escala in np.linspace(0.6, 1.4, 15):
        w, h = int(template.shape[1] * escala), int(template.shape[0] * escala)
        if w > screen_gray.shape[1] or h > screen_gray.shape[0]: continue
        resized = cv2.resize(template, (w, h), interpolation=cv2.INTER_LANCZOS4)
        res = cv2.matchTemplate(screen_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > melhor_val: melhor_val, melhor_loc, dim_vencedora = max_val, max_loc, (w, h)

    if melhor_val >= CONFIANCA_BUSCA:
        off_x, off_y = OFFSETS_ESPECIFICOS.get(img_path, (0, 0))
        abs_x = melhor_loc[0] + (dim_vencedora[0] // 2) + monitor["left"] + off_x
        abs_y = melhor_loc[1] + (dim_vencedora[1] // 2) + monitor["top"] + off_y
        return (abs_x, abs_y)
    return None

def calcular_estoque_seguro(area_coords):
    x, y, w, h = area_coords
    margem = 5
    top = int(max(0, min(SCREEN_H - 1, y + (h * 0.70) + margem)))
    left = int(max(0, min(SCREEN_W - 1, x + margem)))
    width = int(max(1, w - (margem * 2)))
    height = int(max(1, (h * 0.30) - (margem * 2)))
    with mss.mss() as sct:
        try:
            frame = np.array(sct.grab({"top": top, "left": left, "width": width, "height": height}))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            if np.mean(gray) < 35: return 0.0
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return round((cv2.countNonZero(thresh) / (width * height)) * 100, 2)
        except: return 0.0

# --- MOVIMENTAÇÃO ---

def clicar_suave(x, y):
    pydirectinput.moveTo(int(x), int(y), duration=5.0)
    time.sleep(0.5)
    pydirectinput.mouseDown()
    time.sleep(0.5) 
    pydirectinput.mouseUp()
    time.sleep(5.0)

def reset_total():
    for _ in range(12): 
        pydirectinput.press('backspace')
        time.sleep(0.1)

# --- GESTÃO DE CONFIGURAÇÃO ---

def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"coords": [[500, 300, 150, 200] for _ in range(4)]}

def salvar_config(coords, **kwargs):
    config = carregar_config()
    config["coords"] = coords
    for key, value in kwargs.items(): config[key] = value
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

# --- LÓGICA PRINCIPAL ---

def realizar_compras():
    config = carregar_config()
    coords = config["coords"]

    print("\n[V] INICIANDO CICLO DE COMPRA")

    for i in range(len(coords)):
        painel_id = i + 1
        
        # P1 Comentado
        if painel_id == 1: continue

        cd_key = f"p{painel_id}_cooldown_until"
        if time.time() < config.get(cd_key, 0):
            restante = int((config[cd_key] - time.time()) / 60)
            print(f"[-] P{painel_id}: Em Cooldown ({restante} min restantes)")
            continue

        # Setup do Menu
        pydirectinput.moveTo(100, 100, duration=0.5)
        pydirectinput.press('enter')
        time.sleep(3.0) 

        perc = calcular_estoque_seguro(coords[i])
        print(f"[?] P{painel_id}: {perc}% de estoque")
        
        if perc < 15.0:
            print(f"[!] Falta no P{painel_id}. Entrando...")
            clicar_suave(coords[i][0] + coords[i][2]//2, coords[i][1] + coords[i][3]//2)
            time.sleep(3.0) 

            # Sequência 1 a 4
            abortar = False
            for n in range(1, 5):
                res = localizar_escala_dinamica(f"compra_p{painel_id}_{n}.png")
                if res: clicar_suave(res[0], res[1])
                else: 
                    print(f"[X] Imagem {n} não encontrada. Abortando P{painel_id}")
                    abortar = True; break
            
            if not abortar:
                # LÓGICA DA VARIAÇÃO ENTRE IMAGEM 5 E 6
                res_5 = localizar_escala_dinamica(f"compra_p{painel_id}_5.png")
                if res_5:
                    print(f"[+] P{painel_id}: Comprando (Imagem 5)")
                    clicar_suave(res_5[0], res_5[1])
                else:
                    print(f"[*] Imagem 5 não vista. Verificando Imagem 6 (A Caminho)...")
                    res_6 = localizar_escala_dinamica(f"compra_p{painel_id}_6.png")
                    if res_6:
                        print(f"[🕒] Imagem 6 detectada! P{painel_id} em cooldown.")
                        clicar_suave(res_6[0], res_6[1])
                        config[cd_key] = time.time() + TEMPO_COOLDOWN
                        salvar_config(coords, **{cd_key: config[cd_key]})
                    else:
                        print(f"[X] Nenhuma imagem de finalização vista para P{painel_id}")

            reset_total()
        else:
            pydirectinput.press('backspace')
            time.sleep(0.5)

    print("[V] Ciclo Finalizado.")

# --- INTERFACE DE AJUSTE (RESTAURADA) ---

class InterfaceAjuste:
    def __init__(self, coords):
        self.root = tk.Tk()
        self.root.attributes('-alpha', 0.5, '-topmost', True)
        self.root.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")
        self.root.overrideredirect(True)
        self.root.config(bg='black')
        self.root.wm_attributes("-transparentcolor", "black")
        self.canvas = tk.Canvas(self.root, width=SCREEN_W, height=SCREEN_H, bg='black', highlightthickness=0); self.canvas.pack()
        self.coords, self.rects, self.sel, self.mode = coords, [], None, None
        
        for i, (x, y, w, h) in enumerate(self.coords):
            rect = self.canvas.create_rectangle(x, y, x+w, y+h, outline='yellow', width=2)
            hand = self.canvas.create_rectangle(x+w-10, y+h-10, x+w, y+h, fill='white')
            lbl = self.canvas.create_text(x+5, y+5, text=f"P{i+1}", fill="white", font=("Arial", 10, "bold"), anchor="nw")
            self.rects.append({'rect': rect, 'handle': hand, 'label': lbl, 'idx': i})
            
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<Return>", lambda e: self.confirmar())
        self.atualizar()
        self.root.mainloop()

    def atualizar(self):
        for r in self.rects:
            idx = r['idx']
            perc = calcular_estoque_seguro(self.coords[idx])
            self.canvas.itemconfig(r['label'], text=f"P{idx+1}: {perc}%", fill="red" if perc < 15 else "lime")
        self.root.after(400, self.atualizar)

    def on_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)[0]
        for r in self.rects:
            if item == r['handle']: self.sel, self.mode = r, 'resize'; return
            if item == r['rect'] or item == r['label']: self.sel, self.mode = r, 'move'; return

    def on_drag(self, event):
        if not self.sel: return
        i = self.sel['idx']
        if self.mode == 'move':
            w, h = self.coords[i][2], self.coords[i][3]
            self.coords[i][0], self.coords[i][1] = event.x - (w//2), event.y - (h//2)
        elif self.mode == 'resize':
            self.coords[i][2], self.coords[i][3] = event.x - self.coords[i][0], event.y - self.coords[i][1]
        c = self.coords[i]
        self.canvas.coords(self.sel['rect'], c[0], c[1], c[0]+c[2], c[1]+c[3])
        self.canvas.coords(self.sel['handle'], c[0]+c[2]-10, c[1]+c[3]-10, c[0]+c[2], c[1]+c[3])
        self.canvas.coords(self.sel['label'], c[0]+5, c[1]+5)

    def confirmar(self):
        salvar_config(self.coords); self.root.destroy()

# --- LOOP PRINCIPAL ---

def modo_afk():
    print(f"🔄 AFK Ativo. [{CONFIG_KEY.upper()}] Ajustar | [{FORCAR_KEY.upper()}] Forçar | [{STOP_KEY.upper()}] Sair")
    inicio = time.time()
    while time.time() - inicio < TEMPO_AFK:
        if keyboard.is_pressed(STOP_KEY): os._exit(0)
        if keyboard.is_pressed(FORCAR_KEY): return 
        if keyboard.is_pressed(CONFIG_KEY): 
            InterfaceAjuste(carregar_config()["coords"])
            return
        pydirectinput.moveRel(10, 0); time.sleep(0.1); pydirectinput.moveRel(-10, 0); time.sleep(2)

if __name__ == "__main__":
    while True:
        modo_afk()
        realizar_compras()