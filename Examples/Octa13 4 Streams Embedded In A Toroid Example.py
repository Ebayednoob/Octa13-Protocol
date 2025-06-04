import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters for the torus
R = 2      # Major radius
r = 0.6    # Minor radius

# Create figure and 3D axis
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

# Draw semi-transparent torus surface
u = np.linspace(0, 2 * np.pi, 60)
v = np.linspace(0, 2 * np.pi, 30)
U, V = np.meshgrid(u, v)
X = (R + r * np.cos(V)) * np.cos(U)
Y = (R + r * np.cos(V)) * np.sin(U)
Z = r * np.sin(V)
ax.plot_surface(X, Y, Z, color='lightgrey', alpha=0.3, linewidth=0)

# Plot 4 streams as circular rings on the torus
num_streams = 4
nodes_per_stream = 8

for i in range(num_streams):
    # Fixed toroidal latitude for each stream
    vi = (i / num_streams) * 2 * np.pi
    ui = np.linspace(0, 2 * np.pi, 200)
    
    # Parametric equation for the ring
    x_ring = (R + r * np.cos(vi)) * np.cos(ui)
    y_ring = (R + r * np.cos(vi)) * np.sin(ui)
    z_ring = r * np.sin(vi)
    
    # Plot the ring
    ax.plot(x_ring, y_ring, z_ring, linewidth=1, alpha=0.6)
    
    # Plot nodes on each ring
    node_us = np.linspace(0, 2 * np.pi, nodes_per_stream, endpoint=False)
    for j, uj in enumerate(node_us):
        x_node = (R + r * np.cos(vi)) * np.cos(uj)
        y_node = (R + r * np.cos(vi)) * np.sin(uj)
        z_node = r * np.sin(vi)
        
        # Symbol value and frequency mapping (example)
        symbol = j
        frequency = 1 + j  # illustrative frequency index
        size = 20 + 15 * frequency
        
        # Color map based on symbol
        color = plt.cm.viridis(symbol / (nodes_per_stream - 1))
        
        # Plot node
        ax.scatter(x_node, y_node, z_node, s=size, color=color, edgecolor='k', depthshade=True)
        ax.text(x_node, y_node, z_node, str(symbol), fontsize=8, color='k', ha='center', va='center')
        
        # Compute tangent vector for spin arrow
        # Derivative wrt uj only influences the cosine/sine of uj
        tx = - (R + r * np.cos(vi)) * np.sin(uj)
        ty = (R + r * np.cos(vi)) * np.cos(uj)
        tz = 0
        # Normalize tangent
        norm = np.sqrt(tx**2 + ty**2 + tz**2)
        if norm != 0:
            tx, ty, tz = tx / norm, ty / norm, tz / norm
        
        # Plot a small arrow indicating "spin"
        ax.quiver(x_node, y_node, z_node, tx, ty, tz, length=0.3, normalize=True, linewidth=1)

# Set labels and title
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title('Octa13 Streams Embedded in a Toroid\n(4 Streams, Nodes Indicating Symbol, Frequency, Rotation)')

# Adjust view angle
ax.view_init(elev=30, azim=45)

plt.show()
