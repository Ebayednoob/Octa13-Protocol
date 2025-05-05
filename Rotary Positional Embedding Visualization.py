import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 3D Spiral Visualization
positions = np.linspace(0, 4 * np.pi, 200)
radius = 1
x = radius * np.cos(positions)
y = radius * np.sin(positions)
z = positions / (2 * np.pi)  # One full turn per unit height

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.plot(x, y, z)
ax.set_title("3D Spiral Embedding of Positions")
ax.set_xlabel("X (cosθ)")
ax.set_ylabel("Y (sinθ)")
ax.set_zlabel("Position (turns)")
plt.show()

# 2D Circle Embedding for Discrete Positions
theta = np.linspace(0, 2 * np.pi, 12, endpoint=False)
x2 = np.cos(theta)
y2 = np.sin(theta)

fig = plt.figure()
plt.scatter(x2, y2)
for i, angle in enumerate(theta):
    plt.text(x2[i], y2[i], str(i), ha='center', va='center')
plt.title("2D Positional Embeddings on Unit Circle")
plt.xlabel("X (cosθ)")
plt.ylabel("Y (sinθ)")
plt.axis('equal')
plt.show()
