import tkinter as tk
import numpy as np
import heapq
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Initialize main window
root = tk.Tk()
root.title("Semiring Feature Fusion & 3D DP Visualization")
root.geometry("1000x1000")

# Nod layer symbols (3-bit values)
nod_symbols = {
    0: "⬢", 1: "⬡", 2: "◉", 3: "⬣",
    4: "⬠", 5: "⬤", 6: "△", 7: "◯"
}

# Three 8×8 feature grids (integer 0-7 values)
grids = [np.zeros((8, 8), dtype=int) for _ in range(3)]
fused_weights = None
path = None

# Tropical semiring fusion: min(f1 + f2, f3)
def fuse_features(g1, g2, g3):
    return np.minimum(g1 + g2, g3)

# Dijkstra shortest-path on grid
def dijkstra(weights):
    h, w = weights.shape
    dist = np.full((h, w), np.inf)
    prev = {}
    dist[0, 0] = weights[0, 0]
    pq = [(dist[0, 0], (0, 0))]
    dirs = [(1,0), (-1,0), (0,1), (0,-1)]
    while pq:
        d, (y, x) = heapq.heappop(pq)
        if d > dist[y, x]:
            continue
        if (y, x) == (h-1, w-1):
            break
        for dy, dx in dirs:
            ny, nx = y+dy, x+dx
            if 0 <= ny < h and 0 <= nx < w:
                nd = d + weights[ny, nx]
                if nd < dist[ny, nx]:
                    dist[ny, nx] = nd
                    prev[(ny, nx)] = (y, x)
                    heapq.heappush(pq, (nd, (ny, nx)))
    # Reconstruct path
    p = []
    node = (h-1, w-1)
    while True:
        p.append(node)
        if node == (0, 0):
            break
        node = prev.get(node, (0, 0))
    return p[::-1]

# Layout: top for 2x2, mid for buttons, bottom for 3D
top_frame = tk.Frame(root)
top_frame.pack(fill=tk.BOTH, expand=True)
btn_frame = tk.Frame(root)
btn_frame.pack(fill=tk.X)
bottom_frame = tk.Frame(root)
bottom_frame.pack(fill=tk.BOTH, expand=True)

# 2x2 subplot figure
fig1, axes = plt.subplots(2, 2, figsize=(6, 6))
canvas1 = FigureCanvasTkAgg(fig1, master=top_frame)
canvas1.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# 3D figure
fig2 = plt.Figure(figsize=(6, 4))
ax3d = fig2.add_subplot(111, projection='3d')
canvas2 = FigureCanvasTkAgg(fig2, master=bottom_frame)
canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)

def redraw():
    global fused_weights, path
    # Draw 2D feature & fused grids
    for ax in axes.flatten():
        ax.clear()
    titles = ["Feature 1", "Feature 2", "Feature 3"]
    for idx in range(3):
        r, c = divmod(idx, 2)
        ax = axes[r, c]
        grid = grids[idx]
        ax.imshow(grid, cmap="viridis", vmin=0, vmax=7)
        for i in range(8):
            for j in range(8):
                ax.text(j, i, nod_symbols[grid[i, j]],
                        ha="center", va="center", color="white", fontsize=14)
        ax.set_title(titles[idx])
        ax.set_xticks([]); ax.set_yticks([])
    fused_ax = axes[1, 1]
    if fused_weights is not None:
        fused_ax.imshow(fused_weights, cmap="plasma")
        fused_ax.set_title("Fused Weights & Path")
        if path is not None:
            ys, xs = zip(*path)
            fused_ax.plot(xs, ys, marker='o', color='white')
    else:
        fused_ax.set_axis_off()
    fig1.tight_layout()
    canvas1.draw()
    update_3d()

def update_3d():
    ax3d.clear()
    ax3d.set_xlabel("Color (Feature 1)")
    ax3d.set_ylabel("Symbol (Feature 2)")
    ax3d.set_zlabel("Fused Weight")
    if fused_weights is not None:
        # Scatter all pixels
        xs = grids[0].flatten()
        ys = grids[1].flatten()
        zs = fused_weights.flatten()
        ax3d.scatter(xs, ys, zs, alpha=0.5)
        # Plot shortest-path in 3D
        if path is not None:
            pts = [(grids[0][y,x], grids[1][y,x], fused_weights[y,x]) for y,x in path]
            xs_p, ys_p, zs_p = zip(*pts)
            ax3d.plot(xs_p, ys_p, zs_p, color='red', marker='o', linewidth=2)
    canvas2.draw()

def on_click(event):
    global fused_weights, path
    for idx, ax in enumerate(axes.flatten()[:3]):
        if event.inaxes == ax:
            x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
            if 0 <= x < 8 and 0 <= y < 8:
                grids[idx][y, x] = (grids[idx][y, x] + 1) % 8
                fused_weights = None
                path = None
                redraw()
            break

def compute_fusion():
    global fused_weights, path
    fused_weights = fuse_features(grids[0], grids[1], grids[2])
    path = None
    redraw()

def compute_path():
    global fused_weights, path
    if fused_weights is not None:
        path = dijkstra(fused_weights)
        redraw()

def update_all():
    global fused_weights, path
    fused_weights = fuse_features(grids[0], grids[1], grids[2])
    if path:
        path = dijkstra(fused_weights)
    redraw()

def refresh_display():
    redraw()

def reset_all():
    global fused_weights, path
    for g in grids:
        g[:] = 0
    fused_weights = None
    path = None
    redraw()

# Bind clicks and buttons
canvas1.mpl_connect("button_press_event", on_click)
tk.Button(btn_frame, text="Compute Fusion", command=compute_fusion).pack(side=tk.LEFT, padx=5, pady=5)
tk.Button(btn_frame, text="Compute Path", command=compute_path).pack(side=tk.LEFT, padx=5, pady=5)
tk.Button(btn_frame, text="Update", command=update_all).pack(side=tk.LEFT, padx=5, pady=5)
tk.Button(btn_frame, text="Refresh", command=refresh_display).pack(side=tk.LEFT, padx=5, pady=5)
tk.Button(btn_frame, text="Reset", command=reset_all).pack(side=tk.LEFT, padx=5, pady=5)

# Initial draw
redraw()

# Start GUI
root.mainloop()
