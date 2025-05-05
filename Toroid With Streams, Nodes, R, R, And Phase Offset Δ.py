"""//**Example Visualization of Data streams and Nodes**//"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Toroid parameters
R = 2.0  # Major radius
r = 0.6  # Minor radius
S = 4    # Number of streams
Delta = 2 * np.pi / S  # Phase offset between streams
nodes_per_stream = 8

# Create figure and 3D axis
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Plot torus surface
u = np.linspace(0, 2 * np.pi, 100)
v = np.linspace(0, 2 * np.pi, 50)
U, V = np.meshgrid(u, v)
X = (R + r * np.cos(V)) * np.cos(U)
Y = (R + r * np.cos(V)) * np.sin(U)
Z = r * np.sin(V)
ax.plot_surface(X, Y, Z, color='lightgrey', alpha=0.3, linewidth=0)

# Streams and nodes
for s, color in zip([1, 2], ['orange', 'red']):
    offset = Delta * (s - 1)
    # Stream curve
    u_vals = np.linspace(0, 2 * np.pi, 200)
    x_stream = (R + r * np.cos(0)) * np.cos(u_vals + offset)
    y_stream = (R + r * np.cos(0)) * np.sin(u_vals + offset)
    z_stream = r * np.sin(0)
    ax.plot(x_stream, y_stream, z_stream, linewidth=2, color=color, label=f'Stream {s}')
    
    # Nodes on stream
    for j in range(nodes_per_stream):
        uj = offset + 2 * np.pi * j / nodes_per_stream
        x_node = (R + r * np.cos(0)) * np.cos(uj)
        y_node = (R + r * np.cos(0)) * np.sin(uj)
        z_node = r * np.sin(0)
        ax.scatter(x_node, y_node, z_node, s=50, color=color, edgecolor='k')
        ax.text(x_node, y_node, z_node + 0.05, str(j), fontsize=8, color='k', ha='center')

# Highlight phase offset arc between u=0 and u=Delta
u_arc = np.linspace(0, Delta, 100)
x_arc = (R + r * np.cos(0)) * np.cos(u_arc)
y_arc = (R + r * np.cos(0)) * np.sin(u_arc)
z_arc = r * np.sin(0)
ax.plot(x_arc, y_arc, z_arc, linewidth=3, color='magenta', label='Δ Arc')

# Label Δ at midpoint
u_mid = Delta / 2
x_mid = (R + r * np.cos(0)) * np.cos(u_mid)
y_mid = (R + r * np.cos(0)) * np.sin(u_mid)
z_mid = r * np.sin(0)
ax.text(x_mid, y_mid, z_mid + 0.1, 'Δ', fontsize=12, ha='center')

# Draw and label major radius R
ax.quiver(0, 0, 0, R, 0, 0, linewidth=2, arrow_length_ratio=0.1)
ax.text(R/2, 0, 0, 'R', fontsize=12, ha='center')

# Draw and label minor radius r
tube_center = np.array([(R + r * np.cos(0)) * np.cos(0),
                        (R + r * np.cos(0)) * np.sin(0),
                        r * np.sin(0)])
ax.quiver(tube_center[0], tube_center[1], tube_center[2], 
          r, 0, 0, linewidth=2, arrow_length_ratio=0.1)
ax.text(tube_center[0] + r/2, tube_center[1], tube_center[2], 'r', fontsize=12, ha='center')

# Legend and view adjustments
ax.legend()
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title('Toroid with Streams, Nodes, R, r, and Phase Offset Δ')
ax.view_init(elev=30, azim=45)

plt.show()
