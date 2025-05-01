import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
from io import StringIO
import hashlib
from mpl_toolkits.mplot3d import Axes3D

PHI = (1 + 5 ** 0.5) / 2
NODES_PER_STREAM = 12

class OCTA13GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OCTA-13 Protocol GUI with Phi-Vortex Torus")
        self.root.geometry("1800x900")
        self.grid_size = 8
        self.grid_data = self.generate_sierpinski_triangle()
        self.frame = 0
        self.running = False
        self.torus_frame = 0
        self.max_frames = NODES_PER_STREAM
        self.stream_colors = ['red', 'green', 'blue', 'orange']

        self.nod_symbols = {
            0: "⬢", 1: "⬡", 2: "◉", 3: "⬣",
            4: "⬠", 5: "⬤", 6: "△", 7: "◯"
        }

        self.setup_gui()
        self.update_all()

    def generate_sierpinski_triangle(self):
        grid = np.zeros((self.grid_size, self.grid_size), dtype=int)
        for y in range(self.grid_size):
            for x in range(self.grid_size):
                if (x & y) == 0:
                    grid[y, x] = 1
        return grid

    def derive_13bit_key(self):
        flat = self.grid_data.flatten()
        data = ''.join(map(str, flat))
        hashed = hashlib.sha256(data.encode()).hexdigest()
        first_4_hex_digits = hashed[:4]
        key_bin = bin(int(first_4_hex_digits, 16))[2:].zfill(16)[:13]
        return key_bin

    def setup_gui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=False)

        self.fig, self.ax = plt.subplots(figsize=(5, 5))
        self.canvas = FigureCanvasTkAgg(self.fig, master=top_frame)
        self.canvas.get_tk_widget().pack(side=tk.LEFT)

        self.canvas.mpl_connect("button_press_event", self.on_click)

        control_frame = tk.Frame(top_frame)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.play_button = tk.Button(control_frame, text="▶ Play", command=self.play)
        self.play_button.pack()

        self.pause_button = tk.Button(control_frame, text="⏸ Pause", command=self.pause)
        self.pause_button.pack()

        self.stop_button = tk.Button(control_frame, text="⏹ Stop", command=self.stop)
        self.stop_button.pack()

        self.calibrate_button = tk.Button(control_frame, text="🔄 Calibrate", command=self.reset_to_sierpinski)
        self.calibrate_button.pack()

        self.key_label = tk.Label(control_frame, text="13-bit Key: ")
        self.key_label.pack(pady=10)

        self.output_text = tk.Text(self.root, wrap=tk.NONE, height=25)
        self.output_text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.scroll_y = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.output_text.yview)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=self.scroll_y.set)

        self.scroll_x = tk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.output_text.xview)
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.output_text.config(xscrollcommand=self.scroll_x.set)

        self.torus_fig = plt.figure(figsize=(5, 5))
        self.torus_ax = self.torus_fig.add_subplot(111, projection='3d')
        self.torus_canvas = FigureCanvasTkAgg(self.torus_fig, master=top_frame)
        self.torus_canvas.get_tk_widget().pack(side=tk.RIGHT)

        self.ani = animation.FuncAnimation(self.torus_fig, self.animate_torus, interval=1000, blit=False)

    def on_click(self, event):
        if event.inaxes:
            x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
            if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                self.grid_data[y, x] = (self.grid_data[y, x] + 1) % 8
                self.update_all()

    def update_plot(self):
        self.ax.clear()
        self.ax.imshow(self.grid_data, cmap="viridis", vmin=0, vmax=7)
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                symbol = self.nod_symbols[self.grid_data[i, j]]
                self.ax.text(j, i, symbol, va='center', ha='center', color='white', fontsize=16)
        self.ax.set_xticks(np.arange(8))
        self.ax.set_yticks(np.arange(8))
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])
        self.ax.grid(True, color='gray', linestyle='-', linewidth=0.5)
        self.canvas.draw()

    def update_text_output(self):
        packet_records = []
        encoded_packets = []
        for i in range(8):
            for j in range(8):
                nod = self.grid_data[i, j]
                octv = (i + j) % 8
                pos = (i ^ j) % 8
                chk = (octv ^ nod ^ pos) % 8
                end = 1 if i == 0 or j == 0 or i == 7 or j == 7 or i == j else 0
                packet = f'{octv:03b}{nod:03b}{pos:03b}{chk:03b}{end}'
                encoded_packets.append(packet)
                packet_records.append({
                    "Pixel": f"({j},{i})", "OCT": f'{octv:03b}', "NOD": f'{nod:03b}',
                    "POS": f'{pos:03b}', "CHK": f'{chk:03b}', "END": str(end),
                    "Binary": packet, "Symbol": self.nod_symbols[nod]
                })

        packet_df = pd.DataFrame(packet_records)
        grid_df = pd.DataFrame(self.grid_data, columns=[f"X={i}" for i in range(8)])
        grid_df.index = [f"Y={i}" for i in range(8)]

        full_stream = ''.join(encoded_packets)

        buffer = StringIO()
        buffer.write("=== OCTA-13 Packet Table ===\n")
        buffer.write(packet_df.to_string(index=False))
        buffer.write("\n\n=== NOD Layer Grid Data ===\n")
        buffer.write(grid_df.to_string())
        buffer.write(f"\n\n=== Full OCTA-13 Encoded Stream ({len(encoded_packets)} packets × 13 bits) ===\n")
        buffer.write(full_stream)
        buffer.write(f"\nTotal Bits: {len(full_stream)}")

        self.output_text.config(state='normal')
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, buffer.getvalue())
        self.output_text.config(state='disabled')

        self.key_label.config(text=f"13-bit Key: {self.derive_13bit_key()}")

    def update_all(self):
        self.update_plot()
        self.update_text_output()

    def reset_to_sierpinski(self):
        self.grid_data = self.generate_sierpinski_triangle()
        self.update_all()

    def play(self):
        self.running = True
        self.auto_cycle()

    def pause(self):
        self.running = False

    def stop(self):
        self.running = False
        self.frame = 0
        self.torus_frame = 0
        self.update_all()

    def auto_cycle(self):
        if self.running:
            self.frame += 1
            self.torus_frame = (self.torus_frame + 1) % self.max_frames
            self.update_all()
            self.root.after(1000, self.auto_cycle)

    def phi_vortex_indices(self, seed):
        indices = [seed]
        for _ in range(1, NODES_PER_STREAM):
            next_index = (indices[-1] + round(PHI * 9)) % NODES_PER_STREAM
            indices.append(next_index)
        return indices

    def animate_torus(self, i):
        self.torus_ax.clear()
        theta = np.linspace(0, 2 * np.pi, 30)
        phi = np.linspace(0, 2 * np.pi, 30)
        theta, phi = np.meshgrid(theta, phi)
        R, r = 2, 0.8
        X = (R + r * np.cos(theta)) * np.cos(phi)
        Y = (R + r * np.cos(theta)) * np.sin(phi)
        Z = r * np.sin(theta)
        self.torus_ax.plot_surface(X, Y, Z, color='lightblue', alpha=0.3)

        for s in range(4):
            vortex_indices = self.phi_vortex_indices(seed=s * 3)
            phi_vals = [(j * 2 * np.pi / NODES_PER_STREAM) for j in vortex_indices]
            theta_val = (s / 4) * 2 * np.pi
            x_line = [(R + r * np.cos(theta_val)) * np.cos(p) for p in phi_vals]
            y_line = [(R + r * np.cos(theta_val)) * np.sin(p) for p in phi_vals]
            z_line = [r * np.sin(theta_val)] * NODES_PER_STREAM

            self.torus_ax.plot(x_line, y_line, z_line, color=self.stream_colors[s], linewidth=1.5)

            idx = self.torus_frame % NODES_PER_STREAM
            self.torus_ax.scatter(x_line[idx], y_line[idx], z_line[idx], color=self.stream_colors[s], s=80)

        self.torus_ax.view_init(elev=30, azim=(i * 30) % 360)
        self.torus_ax.set_axis_off()
        self.torus_canvas.draw()

root = tk.Tk()
app = OCTA13GUI(root)
root.mainloop()
