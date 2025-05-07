import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import pygame
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D

# Reinitialize mixer explicitly to stereo (2 channels)
pygame.mixer.quit()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
# Retrieve actual initialized channel count
mixer_info = pygame.mixer.get_init()
out_channels = mixer_info[2] if mixer_info else 2
print(f"Pygame mixer init channels: {out_channels}")

def extended_solfeggio():
    return [174, 285, 348, 396, 417, 528, 570, 639, 741, 792, 852, 963]

def equal_tempered():
    base = 396.0
    return [round(base * (2 ** (n / 12)), 1) for n in range(12)]

def phi_ratio():
    base = 174.0
    phi = (1 + 5**0.5) / 2
    return [round(base * (phi ** n)) for n in range(12)]

class CymaticApp:
    def __init__(self, master):
        self.master = master
        master.title("Cymatic 3D Mixer")

        # Frequency system selector
        self.system_var = tk.StringVar()
        systems = ["Extended-Solfeggio", "Equal-Tempered", "Phi-Ratio"]
        self.system_cb = ttk.Combobox(master, textvariable=self.system_var, values=systems)
        self.system_cb.current(0)
        self.system_cb.bind("<<ComboboxSelected>>", self.update_frequencies)
        self.system_cb.pack(pady=10)

        # Frequency listbox and scrollbar
        frame = tk.Frame(master)
        frame.pack()
        self.listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=12, width=25)
        self.listbox.pack(side=tk.LEFT, padx=10)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        # Control buttons
        btn_frame = tk.Frame(master)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Generate", command=self.generate_audio).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Play", command=self.play_audio).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Pause", command=self.pause_audio).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Stop", command=self.stop_audio).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset", command=self.reset).pack(side=tk.LEFT, padx=5)

        # 2D waveform plot
        self.fig2d = Figure(figsize=(8, 3), dpi=100)
        self.ax2d = self.fig2d.add_subplot(111)
        self.canvas2d = FigureCanvasTkAgg(self.fig2d, master=master)
        self.canvas2d.get_tk_widget().pack(pady=5)

        # 3D cymatic surface plot
        self.fig3d = Figure(figsize=(6, 6), dpi=100)
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=master)
        self.canvas3d.get_tk_widget().pack(pady=5)

        # Internal state
        self.frequencies = []
        self.sound = None
        self.channel = None

        self.update_frequencies()

    def update_frequencies(self, event=None):
        sys = self.system_var.get()
        if sys == "Extended-Solfeggio":
            self.frequencies = extended_solfeggio()
        elif sys == "Equal-Tempered":
            self.frequencies = equal_tempered()
        else:
            self.frequencies = phi_ratio()

        self.listbox.delete(0, tk.END)
        for f in self.frequencies:
            label = f"{f:.1f} Hz" if isinstance(f, float) else f"{int(f)} Hz"
            self.listbox.insert(tk.END, label)

    def generate_audio(self):
        sel = self.listbox.curselection()
        if len(sel) != 4:
            messagebox.showerror("Error", "Select exactly 4 frequencies")
            return

        freqs = [self.frequencies[i] for i in sel]
        duration, sr = 5, 44100
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        wave = sum(np.sin(2 * np.pi * f * t) for f in freqs)
        wave /= np.max(np.abs(wave)) if np.max(np.abs(wave)) > 0 else 1

        pcm = np.int16(wave * 32767)
        # Tile PCM across actual output channels
        arr = np.tile(pcm[:, None], (1, out_channels)).copy()
        self.sound = pygame.sndarray.make_sound(arr)

        # Update 2D plot
        self.ax2d.clear()
        self.ax2d.plot(t[:1000], wave[:1000])
        self.ax2d.set_title("Waveform (first 1000 samples)")
        self.canvas2d.draw()

        # Update 3D cymatic surface
        X = np.linspace(-1, 1, 100)
        X, Y = np.meshgrid(X, X)
        mix = np.prod([np.sin(2 * np.pi * f * (X + Y)) for f in freqs], axis=0)
        gauss = np.exp(-(X**2 + Y**2) / (2 * 0.5**2))
        Z = mix * gauss
        self.ax3d.clear()
        self.ax3d.plot_surface(X, Y, Z, rstride=2, cstride=2, linewidth=0)
        self.ax3d.set_title("3D Cymatic Surface")
        self.canvas3d.draw()

    def play_audio(self):
        if self.sound:
            self.channel = self.sound.play(loops=-1)

    def pause_audio(self):
        if self.channel:
            self.channel.pause()

    def stop_audio(self):
        if self.channel:
            self.channel.stop()

    def reset(self):
        if self.channel:
            self.channel.stop()
        self.listbox.selection_clear(0, tk.END)
        self.sound = None
        self.ax2d.clear()
        self.ax3d.clear()
        self.canvas2d.draw()
        self.canvas3d.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = CymaticApp(root)
    root.mainloop()
