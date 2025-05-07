import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import pygame
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D

# Initialize pygame mixer for stereo
pygame.mixer.quit()
pygame.mixer.init(frequency=44100, size=-16, channels=2)
init_info = pygame.mixer.get_init()
out_channels = init_info[2] if init_info else 2
print(f"Pygame mixer output channels: {out_channels}")

# Frequency systems with optional base input
def extended_solfeggio():
    return [174, 285, 348, 396, 417, 528, 570, 639, 741, 792, 852, 963]

def equal_tempered(base=396.0):
    return [round(base * (2 ** (n / 12)), 1) for n in range(12)]

def phi_ratio(base=174.0):
    phi = (1 + 5**0.5) / 2
    return [round(base * (phi ** n)) for n in range(12)]

class CymaticApp:
    def __init__(self, master):
        self.master = master
        master.title("Cymatic Mixer with Octa13 Stream Monitor")

        # --- Controls Frame ---
        ctrl = tk.Frame(master)
        ctrl.pack(padx=10, pady=5, fill='x')

        tk.Label(ctrl, text="Base Frequency (Hz, optional):").grid(row=0, column=0, sticky='w')
        self.base_entry = tk.Entry(ctrl)
        self.base_entry.grid(row=0, column=1, sticky='w')

        tk.Label(ctrl, text="Scale System:").grid(row=1, column=0, sticky='w')
        self.system_var = tk.StringVar()
        self.system_cb = ttk.Combobox(
            ctrl, textvariable=self.system_var,
            values=["Extended-Solfeggio", "Equal-Tempered", "Phi-Ratio"], width=16
        )
        self.system_cb.current(0)
        self.system_cb.grid(row=1, column=1, sticky='w')
        self.system_cb.bind("<<ComboboxSelected>>", self.update_frequencies)

        # Frequency list
        tk.Label(ctrl, text="Select 4 Frequencies:").grid(row=0, column=2, padx=(20,0), sticky='w')
        frame_list = tk.Frame(ctrl)
        frame_list.grid(row=1, column=2, padx=(20,0), rowspan=2)
        self.listbox = tk.Listbox(frame_list, selectmode=tk.MULTIPLE, height=6, width=20)
        self.listbox.pack(side=tk.LEFT)
        sb = tk.Scrollbar(frame_list, orient='vertical', command=self.listbox.yview)
        sb.pack(side=tk.RIGHT, fill='y')
        self.listbox.config(yscrollcommand=sb.set)

        # Volume
        tk.Label(ctrl, text="Volume:").grid(row=0, column=3, padx=(20,0), sticky='w')
        self.volume_var = tk.DoubleVar(value=1.0)
        self.volume_slider = tk.Scale(
            ctrl, variable=self.volume_var, from_=0.0, to=1.0, resolution=0.01,
            orient='horizontal', length=150, command=self.change_volume
        )
        self.volume_slider.grid(row=1, column=3, padx=(20,0))

        # Buttons
        btns = tk.Frame(ctrl)
        btns.grid(row=2, column=3, padx=(20,0), sticky='e')
        for txt, cmd in [("Generate", self.generate_audio), ("Play", self.play_audio),
                         ("Pause", self.pause_audio), ("Stop", self.stop_audio), ("Reset", self.reset)]:
            tk.Button(btns, text=txt, command=cmd, width=6).pack(side='left', padx=2)

        # --- Display Frame ---
        disp = tk.Frame(master)
        disp.pack(padx=10, pady=5, fill='both', expand=True)

        # Top: 2D waveform and Octa13 stream side by side
        top = tk.Frame(disp)
        top.pack(fill='x', pady=5)

        # Waveform canvas
        self.fig2d = Figure(figsize=(4,2), dpi=100)
        self.ax2d = self.fig2d.add_subplot(111)
        self.canvas2d = FigureCanvasTkAgg(self.fig2d, master=top)
        self.canvas2d.get_tk_widget().pack(side='left', fill='both', expand=True)

        # Octa13 text stream
        text_frame = tk.Frame(top)
        text_frame.pack(side='left', padx=10, fill='y')
        tk.Label(text_frame, text="Octa13 Output Stream:").pack(anchor='nw')
        self.octa_text = tk.Text(text_frame, height=6, width=30)
        self.octa_text.pack(fill='y')
        t_sb = tk.Scrollbar(text_frame, orient='vertical', command=self.octa_text.yview)
        t_sb.pack(side='right', fill='y')
        self.octa_text.config(yscrollcommand=t_sb.set)

        # Bottom: 3D cymatic surface
        self.fig3d = Figure(figsize=(4,4), dpi=100)
        self.ax3d = self.fig3d.add_subplot(111, projection='3d')
        self.canvas3d = FigureCanvasTkAgg(self.fig3d, master=disp)
        self.canvas3d.get_tk_widget().pack(pady=5, fill='both', expand=True)

        # Internal state
        self.frequencies = []
        self.sound = None
        self.channel = None

        self.update_frequencies()

    # --- Octa13 helper methods ---
    def compute_crc3(self, bits9: str) -> str:
        s = sum(int(b) for b in bits9) % 8
        return f"{s:03b}"

    def build_octaword(self, octave_idx: int, node_bits: str = '110', role_bits: str = '100', frame_marker: str = '10') -> str:
        oct_bits = f"{octave_idx:03b}"
        bits1_9 = oct_bits + node_bits + role_bits
        crc = self.compute_crc3(bits1_9)
        return bits1_9 + crc + frame_marker

    def generate_octastream(self, selected_indices) -> str:
        words = [self.build_octaword(i) for i in selected_indices]
        return ' '.join(words)
    # --- End Octa13 helper methods ---

    # Core methods
    def update_frequencies(self, event=None):
        base_text = self.base_entry.get().strip()
        try:
            base_val = float(base_text)
        except ValueError:
            base_val = None
        sys = self.system_var.get()
        if sys == "Extended-Solfeggio":
            self.frequencies = extended_solfeggio()
        elif sys == "Equal-Tempered":
            self.frequencies = equal_tempered(base_val) if base_val else equal_tempered()
        else:
            self.frequencies = phi_ratio(base_val) if base_val else phi_ratio()
        self.listbox.delete(0, 'end')
        for f in self.frequencies:
            label = f"{f:.1f} Hz" if isinstance(f, float) else f"{int(f)} Hz"
            self.listbox.insert('end', label)

    def generate_audio(self):
        sel = self.listbox.curselection()
        if len(sel) != 4:
            messagebox.showerror("Error", "Select exactly 4 frequencies")
            return
        freqs = [self.frequencies[i] for i in sel]
        sr = 44100; dur = 5
        t = np.linspace(0, dur, int(sr*dur), endpoint=False)
        wave = sum(np.sin(2*np.pi*f*t) for f in freqs)
        wave /= np.max(np.abs(wave)) if np.max(np.abs(wave))>0 else 1
        pcm = np.int16(wave*32767)
        arr = np.tile(pcm[:,None], (1, out_channels)).copy()
        self.sound = pygame.sndarray.make_sound(arr)
        self.sound.set_volume(self.volume_var.get())
        # Octa13
        stream = self.generate_octastream(sel)
        self.octa_text.delete('1.0','end'); self.octa_text.insert('end', stream)
        # Waveform
        self.ax2d.clear(); self.ax2d.plot(t[:1000], wave[:1000])
        self.ax2d.set_title("Waveform Preview")
        self.canvas2d.draw()
        # 3D
        X = np.linspace(-1,1,100); X, Y = np.meshgrid(X,X)
        mix = np.prod([np.sin(2*np.pi*f*(X+Y)) for f in freqs], axis=0)
        gauss = np.exp(-(X**2+Y**2)/(2*0.5**2)); Z = mix*gauss
        self.ax3d.clear(); self.ax3d.plot_surface(X,Y,Z,rstride=2,cstride=2,linewidth=0)
        self.ax3d.set_title("3D Cymatic Surface")
        self.canvas3d.draw()

    def play_audio(self):
        if self.sound:
            self.channel = self.sound.play(loops=-1)
            self.channel.set_volume(self.volume_var.get())

    def change_volume(self, val):
        v = float(val)
        if self.sound: self.sound.set_volume(v)
        if self.channel: self.channel.set_volume(v)

    def pause_audio(self):
        if self.channel: self.channel.pause()

    def stop_audio(self):
        if self.channel: self.channel.stop()

    def reset(self):
        if self.channel: self.channel.stop()
        self.listbox.selection_clear(0,'end')
        self.octa_text.delete('1.0','end')
        self.ax2d.clear(); self.canvas2d.draw()
        self.ax3d.clear(); self.canvas3d.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = CymaticApp(root)
    root.mainloop()
