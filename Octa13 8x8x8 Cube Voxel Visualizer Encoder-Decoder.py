import tkinter as tk
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import matplotlib.colors as mcolors
import pandas as pd
from io import StringIO
import hashlib

class OCTA13GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OCTA-13 Protocol GUI with 3D Data Cube")
        self.root.geometry("1800x900")
        self.grid_size = 8
        self.grid_data = self.generate_sierpinski_triangle()
        self.frame = 0
        self.running = False

        self.nod_symbols = {
            0: "⬢", 1: "⬡", 2: "◉", 3: "⬣",
            4: "⬠", 5: "⬤", 6: "△", 7: "◯"
        }
        self.colors = list(mcolors.TABLEAU_COLORS.values())

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

        self.cube_fig = plt.figure(figsize=(6, 6))
        self.cube_ax = self.cube_fig.add_subplot(111, projection='3d')
        self.cube_canvas = FigureCanvasTkAgg(self.cube_fig, master=top_frame)
        self.cube_canvas.get_tk_widget().pack(side=tk.RIGHT)

        self.ani = animation.FuncAnimation(self.cube_fig, self.animate_cube, interval=1000, blit=False)

    def on_click(self, event):
        if event.inaxes:
            x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
            if 0 <= x < 8 and 0 <= y < 8:
                self.grid_data[y, x] = (self.grid_data[y, x] + 1) % 8
                self.update_all()

    def update_plot(self):
        self.ax.clear()
        self.ax.imshow(self.grid_data, cmap="viridis", vmin=0, vmax=7)
        for i in range(8):
            for j in range(8):
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
        self.update_all()

    def auto_cycle(self):
        if self.running:
            self.frame += 1
            self.update_all()
            self.root.after(1000, self.auto_cycle)

    def draw_colored_box(self, x, y, z, color):
        r = [0, 1]
        vertices = np.array([[x + dx, y + dy, z + dz] for dx in r for dy in r for dz in r])
        edges = [
            [vertices[0], vertices[1], vertices[3], vertices[2]],
            [vertices[4], vertices[5], vertices[7], vertices[6]],
            [vertices[0], vertices[1], vertices[5], vertices[4]],
            [vertices[2], vertices[3], vertices[7], vertices[6]],
            [vertices[1], vertices[3], vertices[7], vertices[5]],
            [vertices[0], vertices[2], vertices[6], vertices[4]]
        ]
        box = Poly3DCollection(edges, facecolors=color, edgecolors='black', linewidths=0.2, alpha=0.05)
        self.cube_ax.add_collection3d(box)

    def animate_cube(self, i):
        self.cube_ax.clear()
        self.cube_ax.set_xlim([0, 8])
        self.cube_ax.set_ylim([0, 8])
        self.cube_ax.set_zlim([0, 8])

        for x in range(8):
            for y in range(8):
                symbol_value = self.grid_data[y, x]
                symbol = self.nod_symbols[symbol_value]
                color = self.colors[symbol_value % len(self.colors)]
                for z in range(8):
                    self.cube_ax.text(x + 0.5, y + 0.5, z + 0.5, symbol, fontsize=10, ha='center', va='center')
                    self.draw_colored_box(x, y, z, color)

        self.cube_ax.view_init(elev=30, azim=(i * 10) % 360)
        self.cube_ax.set_axis_off()
        self.cube_canvas.draw()

root = tk.Tk()
app = OCTA13GUI(root)
root.mainloop()
