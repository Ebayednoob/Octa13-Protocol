import tkinter as tk
from tkinter import ttk  # For OptionMenu, Notebook, Scale and better styling if needed
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.patches as patches  # For drawing polygons/shapes
import matplotlib.patheffects as path_effects  # Import for path effects
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # For 3D polygons
import tkinter.scrolledtext as scrolledtext
from collections import deque  # For destination node traces
from PIL import Image, ImageTk, ImageDraw
import math
import json
import sys
import socket
import threading
import struct # For creating binary data


# Constants
R_TORUS = 5
r_TORUS = 2
NUM_POINTS_TORUS = 100
TRACE_LENGTH = 12  # For stream path visualization

# Octa13 symbolic elements
symbols = ["⬢", "⬡", "◉", "⬣", "⬠", "⬤", "△", "◯"]
colors = ["#FF0000", "#0000FF", "#00FF00", "#FFFF00", "#FF00FF", "#00FFFF", "#FF69B4", "#FFFFFF"]  # Hex colors
spins = ["→", "↺", "↻", "∞", "⇅", "⇆", "⤡", "⟳"]

ELEMENT_COUNT = len(symbols)
if not (len(colors) == ELEMENT_COUNT and len(spins) == ELEMENT_COUNT):
    raise ValueError("Symbols, colors, and spins lists must have the same number of elements.")

# Transmission Simulation Constants
DESTINATION_NODE_COLOR_DEFAULT = "cyan"
DESTINATION_NODE_COLOR_FLASH = "white"
DESTINATION_NODE_SIZE = 180
DESTINATION_NODE_TRACE_LENGTH = 6
NODE_FLASH_DURATION_FRAMES = 5

# Base9 System for Toroid
NUM_DISCRETE_U_STEPS = 9

# Polygon definitions for the "Symbolic Representation Explorer" tab
polygon_definitions = {
    "⬢": {'type': 'polygon', 'sides': 6, 'label': 'Hexagon', 'unicode_char': "⬢"},
    "⬡": {'type': 'polygon', 'sides': 6, 'label': 'Hex. Outline', 'unicode_char': "⬡", 'fill': False, 'edge_only': True},
    "◉": {'type': 'circle', 'label': 'Circ. w/ Dot', 'unicode_char': "◉", 'inner_dot': True},
    "⬣": {'type': 'polygon', 'sides': 6, 'label': 'Horiz. Hex.', 'unicode_char': "⬣", 'rotation_angle': np.pi / 2},
    "⬠": {'type': 'polygon', 'sides': 5, 'label': 'Pentagon', 'unicode_char': "⬠"},
    "⬤": {'type': 'circle', 'label': 'Filled Circle', 'unicode_char': "⬤"},
    "△": {'type': 'polygon', 'sides': 3, 'label': 'Triangle', 'unicode_char': "△"},
    "◯": {'type': 'circle', 'label': 'Empty Circle', 'unicode_char': "◯", 'fill': False, 'edge_only': True}
}


def torus_coords(u, v, R_param, r_param):
    """Calculates 3D coordinates for a point on a torus."""
    x = (R_param + r_param * np.cos(v)) * np.cos(u)
    y = (R_param + r_param * np.cos(v)) * np.sin(u)
    z = r_param * np.sin(v)
    return x, y, z


def generate_octa13_packet_data(stream_id, frame_index, num_streams_total):
    """
    Generates a standard Octa13 packet (symbol, color, spin) and its torus coordinates,
    incorporating the base9 system for the u-coordinate.
    """
    symbol_idx = (frame_index + stream_id) % ELEMENT_COUNT
    symbol_char = symbols[symbol_idx]
    color_val = colors[symbol_idx]
    spin_char = spins[symbol_idx]

    # Distribute streams more evenly for different counts
    if num_streams_total > 0:
        initial_u_offset_steps = stream_id * (NUM_DISCRETE_U_STEPS / num_streams_total)
        current_u_discrete_step = (frame_index + initial_u_offset_steps) % NUM_DISCRETE_U_STEPS
        u = current_u_discrete_step * (2 * np.pi / NUM_DISCRETE_U_STEPS)
        v = (((frame_index // ELEMENT_COUNT) * np.pi / 8) + stream_id * (np.pi / num_streams_total * 0.5)) % (2 * np.pi)
    else:
        u, v = 0, 0

    return symbol_char, color_val, spin_char, u, v


class OCTA13Visualizer:
    def __init__(self, root_window, stream_mode='tcp', host='localhost', port=9999):
        self.root = root_window
        self.root.title("OCTA-13 Protocol Interactive Visualizer")
        self.root.configure(bg="black")
        self.root.geometry("1600x1080")
        self.root.minsize(1400, 900)

        self.frame_index = 0
        self.running = False

        # --- Dynamic Stream Count & GUI State Variables ---
        self.num_streams_var = tk.IntVar(value=4)
        self.num_active_streams = self.num_streams_var.get()
        self.animation_delay_ms = tk.IntVar(value=300)
        self.selected_stream_var = tk.IntVar(value=1)

        # --- Video Analysis Tab State ---
        self.video_frames = []
        self.video_frame_index = tk.IntVar(value=0)
        self.video_running = False
        self.semantic_codex = {
            "Low Motion": 3,  # Triangle
            "Medium Motion": 6,  # Hexagon
            "High Motion": 5,  # Pentagon
        }

        # --- These will be initialized dynamically ---
        self.stream_overrides = []
        self.trace_history = []
        self.symbol_codex_entries = {}
        self.color_codex_entries = {}
        self.spin_codex_entries = {}
        self.destination_transmission_nodes = []
        
        # --- Conceptual VQ-VAE models for analysis tab ---
        self.analysis_vq_models = []

        # Variables for Symbolic Representation Explorer
        self.selected_explorer_symbol = tk.StringVar(value=symbols[0])
        self.explorer_color_hex = tk.StringVar(value="#61DAFB")
        self.selected_explorer_spin = tk.StringVar(value=spins[0])
        self.explorer_intermediate_points_var = tk.IntVar(value=0)

        # --- Data Streaming Setup ---
        self.stream_mode = stream_mode
        self.binary_stream_mode = tk.BooleanVar(value=False) # Add a variable for binary mode
        if self.stream_mode == 'tcp':
            self.server_socket = None
            self.client_sockets = []
            self.lock = threading.Lock()
            self.start_tcp_server(host, port)

        self.build_gui()
        self.reset_simulation_state()
        self._update_explorer_polygon_visualization()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _initialize_dynamic_structures(self):
        self.num_active_streams = self.num_streams_var.get()
        self.stream_overrides = [None] * self.num_active_streams
        self.trace_history = [[] for _ in range(self.num_active_streams)]
        self.destination_transmission_nodes = []
        for i in range(self.num_active_streams):
            u_pos = (i * 2 * np.pi / self.num_active_streams) + np.pi / 2 if self.num_active_streams > 0 else 0
            v_pos = np.pi / 2 + (i % 2) * np.pi / 4
            self.destination_transmission_nodes.append({
                'id': f"DestNode-{i}", 'stream_index_source': i, 'u': u_pos, 'v': v_pos,
                'flash_timer': 0, 'received_symbol_trace': deque(maxlen=DESTINATION_NODE_TRACE_LENGTH)
            })
            
        # Initialize conceptual VQ models for each stream
        self.analysis_vq_models = []
        for i in range(self.num_active_streams):
             np.random.seed(i) # Make it deterministic per stream
             self.analysis_vq_models.append({
                'latent_dim_h': 4, 'latent_dim_w': 4,
                'codebook': np.random.rand(16, 3) * 255
             })
             
        self.selected_stream_var.set(1)

    def build_gui(self):
        """Constructs the entire GUI structure."""

        style = ttk.Style()
        try:
            available_themes = style.theme_names()
            if 'clam' in available_themes: style.theme_use('clam')
            elif 'alt' in available_themes: style.theme_use('alt')
        except tk.TclError:
            print("TTK themes not available.")

        top_ctrl_bar = tk.Frame(self.root, bg="black", pady=5)
        top_ctrl_bar.pack(side=tk.TOP, fill=tk.X)

        # --- Main Controls ---
        main_ctrl_frame = tk.Frame(top_ctrl_bar, bg="black")
        main_ctrl_frame.pack(side=tk.LEFT, padx=10)
        tk.Button(main_ctrl_frame, text="Play", command=self.start_animation, bg="#282c34", fg="white", padx=10, pady=5,
                  relief=tk.FLAT, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(main_ctrl_frame, text="Pause", command=self.pause_animation, bg="#282c34", fg="white", padx=10,
                  pady=5, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(main_ctrl_frame, text="Reset", command=self.reset_simulation_state, bg="#282c34", fg="white",
                  padx=10, pady=5, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # --- Stream Count Control ---
        stream_count_frame = tk.Frame(top_ctrl_bar, bg="black")
        stream_count_frame.pack(side=tk.LEFT, padx=20)
        tk.Label(stream_count_frame, text="Active Streams:", fg="white", bg="black", font=("Arial", 10)).pack(
            side=tk.LEFT)
        self.num_streams_scale = tk.Scale(stream_count_frame, from_=1, to=9, orient=tk.HORIZONTAL,
                                          variable=self.num_streams_var,
                                          bg="#282c34", fg="white", troughcolor="black", highlightthickness=0,
                                          length=120)
        self.num_streams_scale.pack(side=tk.LEFT)
        tk.Button(stream_count_frame, text="Apply & Reset", command=self.reset_simulation_state, bg="#61afef",
                  fg="black", padx=5, pady=2, relief=tk.FLAT, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=5)

        # --- Frequency Control ---
        freq_ctrl_frame = tk.Frame(top_ctrl_bar, bg="black")
        freq_ctrl_frame.pack(side=tk.LEFT, padx=20)
        tk.Label(freq_ctrl_frame, text="Cycle Freq (ms):", fg="white", bg="black", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=(0, 5))
        self.freq_slider = tk.Scale(freq_ctrl_frame, from_=50, to=1000, orient=tk.HORIZONTAL,
                                    variable=self.animation_delay_ms,
                                    bg="#282c34", fg="white", troughcolor="black", highlightthickness=0, length=150)
        self.freq_slider.pack(side=tk.LEFT)

        # --- Override Controls ---
        self.override_controls_frame = tk.Frame(self.root, bg="black", pady=10)
        self.override_controls_frame.pack(side=tk.TOP, fill=tk.X)

        self.notebook = ttk.Notebook(self.root)
        style.configure('TNotebook.Tab', padding=[10, 5], font=('Arial', 10, 'bold'), foreground=['black'])
        style.map('TNotebook.Tab', foreground=[('selected', '#61dafb')], background=[('selected', '#282c34')])
        style.configure('TNotebook', background='black', borderwidth=0)

        # --- Build all tabs ---
        self._build_visualizer_tab()
        self._build_packet_data_tab()
        self._build_codex_tab()
        self._build_transmission_tab()
        self._build_tcp_output_tab() # New Tab
        self._build_mission_tab()
        self._build_explorer_tab()
        self._build_quaternion_tab()
        self._build_polygon_analysis_tab()
        self._build_video_analysis_tab()
        self._build_falcon_security_tab()
        self._build_architecture_tab()

        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_override_controls(self):
        # Clear existing controls
        for widget in self.override_controls_frame.winfo_children():
            widget.destroy()

        tk.Label(self.override_controls_frame, text="Influence Stream:", fg="white", bg="black",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 5))

        self.selected_stream_var.set(1)  # Reset selection
        for i in range(self.num_active_streams):
            rb = tk.Radiobutton(self.override_controls_frame, text=f"{i + 1}", variable=self.selected_stream_var,
                                value=i + 1,
                                fg="#61dafb", bg="black", selectcolor="black", activebackground="black",
                                activeforeground="#61dafb", font=("Arial", 10))
            rb.pack(side=tk.LEFT)

        tk.Label(self.override_controls_frame, text="Override Symbol:", fg="white", bg="black",
                 font=("Arial", 10)).pack(side=tk.LEFT, padx=(20, 5))
        self.override_symbol_var = tk.StringVar(value=symbols[0])

        style = ttk.Style()
        style.configure('TMenubutton', background='black', foreground='white', font=("Arial", 10),
                        arrowcolor='white')
        style.map('TMenubutton', background=[('active', '#333333')])
        symbol_menu = ttk.OptionMenu(self.override_controls_frame, self.override_symbol_var, symbols[0], *symbols,
                                     style='TMenubutton')
        symbol_menu.pack(side=tk.LEFT, padx=5)

        tk.Button(self.override_controls_frame, text="Apply Override", command=self.apply_override, bg="#61afef",
                  fg="black", padx=10, pady=2, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Button(self.override_controls_frame, text="Clear Selected", command=self.clear_override_for_selected_stream,
                  bg="#e06c75", fg="black", padx=10, pady=2, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(
            side=tk.LEFT, padx=5)
        tk.Button(self.override_controls_frame, text="Clear All", command=self.clear_all_overrides, bg="#e06c75",
                  fg="black", padx=10, pady=2, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

    def _rebuild_stream_gui_elements(self):
        # --- Rebuild Stream Panels in Visualizer Tab ---
        for widget in self.panel_frame.winfo_children():
            widget.destroy()
        self.stream_labels_in_panel = []
        for i in range(self.num_active_streams):
            frame = tk.LabelFrame(self.panel_frame, text=f"Stream {i + 1}", fg="white", bg="black",
                                  font=("Courier New", 11, "bold"), relief=tk.SOLID, borderwidth=1)
            # Adjust grid layout for more streams
            rows = (self.num_active_streams + 1) // 2
            frame.grid(row=i % rows, column=i // rows, padx=5, pady=5, sticky="nsew")
            self.panel_frame.grid_columnconfigure(i // rows, weight=1)
            self.panel_frame.grid_rowconfigure(i % rows, weight=1)
            label_list = []
            for _ in range(TRACE_LENGTH):
                label = tk.Label(frame, text="-", fg="white", bg="black", font=("Courier New", 9), anchor="w",
                                 justify=tk.LEFT)
                label.pack(fill=tk.X, padx=5)
                label_list.append(label)
            self.stream_labels_in_panel.append(label_list)

        # --- Rebuild Analysis Windows ---
        analysis_area = self.analysis_area_frame
        for widget in analysis_area.winfo_children():
            widget.destroy()
        self.analysis_canvases = []
        cols = 3 if self.num_active_streams <= 6 else 4
        for i in range(self.num_active_streams):
            analysis_frame = tk.LabelFrame(analysis_area, text=f"Stream {i + 1} Vertex", fg="white", bg="black",
                                           font=("Arial", 10, "bold"), relief=tk.SOLID, borderwidth=1, padx=5, pady=5)
            analysis_frame.grid(row=i // cols, column=i % cols, padx=5, pady=5, sticky="nsew")
            analysis_area.grid_columnconfigure(i % cols, weight=1)
            analysis_area.grid_rowconfigure(i // cols, weight=1)

            sub_canvases = {}
            panel_titles = ["Vertex Symbol", "Latent Space (VQ)", "Reconstructed"]
            for j, title in enumerate(panel_titles):
                sub_frame = tk.Frame(analysis_frame, bg="black")
                sub_frame.grid(row=0, column=j, sticky="nsew", padx=5)
                analysis_frame.grid_columnconfigure(j, weight=1)

                tk.Label(sub_frame, text=title, fg="lightgrey", bg="black", font=("Arial", 8)).pack()
                canvas = tk.Canvas(sub_frame, width=100, height=100, bg="#1c1e22", highlightthickness=0)
                canvas.pack()
                sub_canvases[title] = canvas
            self.analysis_canvases.append(sub_canvases)

        # --- Rebuild Override Controls ---
        self._build_override_controls()

    def _build_visualizer_tab(self):
        visualizer_tab_frame = tk.Frame(self.notebook, bg="black")
        self.notebook.add(visualizer_tab_frame, text='Visualizer')
        main_viz_frame = tk.Frame(visualizer_tab_frame, bg="black")
        main_viz_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.torus_canvas_frame = tk.Frame(main_viz_frame, bg="black")
        self.torus_canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.fig_torus = plt.Figure(figsize=(8, 6), dpi=100, facecolor='black')
        self.ax_torus = self.fig_torus.add_subplot(111, projection='3d')
        self.canvas_torus_widget = FigureCanvasTkAgg(self.fig_torus, master=self.torus_canvas_frame)
        self.canvas_torus_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.panel_frame = tk.Frame(main_viz_frame, bg="black", padx=10)
        self.panel_frame.pack(side=tk.RIGHT, fill=tk.Y)

        gaussian_plot_frame = tk.Frame(visualizer_tab_frame, bg="black", pady=5)
        gaussian_plot_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.fig_gaussian = plt.Figure(figsize=(6, 3.5), dpi=100, facecolor='black')
        self.ax_gaussian = self.fig_gaussian.add_subplot(111, projection='3d')
        self.canvas_gaussian_widget = FigureCanvasTkAgg(self.fig_gaussian, master=gaussian_plot_frame)
        self.canvas_gaussian_widget.get_tk_widget().pack(fill=tk.X, expand=False, pady=(0, 5))
        self.fig_torus.tight_layout(pad=0.5)
        self.fig_gaussian.tight_layout(pad=0.5)

    def _build_packet_data_tab(self):
        packet_data_tab_frame = tk.Frame(self.notebook, bg="black", padx=10, pady=10)
        self.notebook.add(packet_data_tab_frame, text='Packet Data')
        self.packet_data_text = scrolledtext.ScrolledText(packet_data_tab_frame, wrap=tk.WORD, bg="#1c1e22",
                                                        fg="white", font=("Courier New", 10), relief=tk.FLAT,
                                                        borderwidth=0)
        self.packet_data_text.pack(fill=tk.BOTH, expand=True)
        self.packet_data_text.config(state=tk.DISABLED)

    def _build_codex_tab(self):
        codex_tab_frame_outer = tk.Frame(self.notebook, bg="black")
        self.notebook.add(codex_tab_frame_outer, text='Symbolic Codex')
        codex_canvas = tk.Canvas(codex_tab_frame_outer, bg="black", highlightthickness=0)
        codex_scrollbar = ttk.Scrollbar(codex_tab_frame_outer, orient="vertical", command=codex_canvas.yview)
        codex_scrollable_frame = tk.Frame(codex_canvas, bg="black")
        codex_scrollable_frame.bind("<Configure>", lambda e: codex_canvas.configure(scrollregion=codex_canvas.bbox("all")))
        codex_canvas.create_window((0, 0), window=codex_scrollable_frame, anchor="nw")
        codex_canvas.configure(yscrollcommand=codex_scrollbar.set)
        codex_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        codex_scrollbar.pack(side="right", fill="y")
        codex_definition_frame = tk.Frame(codex_scrollable_frame, bg="black", padx=10, pady=10)
        codex_definition_frame.pack(fill=tk.X, expand=True)
        row_idx = 0
        tk.Label(codex_definition_frame, text="Define Symbol Meanings:", fg="#61dafb", bg="black",
                 font=("Arial", 12, "bold")).grid(row=row_idx, column=0, columnspan=3, sticky="w", pady=(0, 5))
        row_idx += 1
        for i, sym_char in enumerate(symbols):
            tk.Label(codex_definition_frame, text=f"{sym_char}:", fg="white", bg="black",
                     font=("Arial", 10, "bold")).grid(row=row_idx + i, column=0, sticky="e", padx=5)
            entry = tk.Entry(codex_definition_frame, width=40, bg="#282c34", fg="white", relief=tk.FLAT,
                             insertbackground="white")
            entry.grid(row=row_idx + i, column=1, sticky="ew", pady=2)
            self.symbol_codex_entries[sym_char] = entry
        row_idx += len(symbols)
        ttk.Separator(codex_definition_frame, orient='horizontal').grid(row=row_idx, column=0, columnspan=3,
                                                                      sticky='ew', pady=10)
        row_idx += 1
        tk.Label(codex_definition_frame, text="Define Color Meanings (Hex):", fg="#61dafb", bg="black",
                 font=("Arial", 12, "bold")).grid(row=row_idx, column=0, columnspan=3, sticky="w", pady=(0, 5))
        row_idx += 1
        for i, col_hex in enumerate(colors):
            color_label_frame = tk.Frame(codex_definition_frame, bg="black")
            color_label_frame.grid(row=row_idx + i, column=0, sticky="e", padx=5)
            tk.Label(color_label_frame, text="  ", bg=col_hex).pack(side=tk.LEFT)
            tk.Label(color_label_frame, text=f"{col_hex}:", fg="white", bg="black", font=("Arial", 10)).pack(
                side=tk.LEFT)
            entry = tk.Entry(codex_definition_frame, width=40, bg="#282c34", fg="white", relief=tk.FLAT,
                             insertbackground="white")
            entry.grid(row=row_idx + i, column=1, sticky="ew", pady=2)
            self.color_codex_entries[col_hex] = entry
        row_idx += len(colors)
        ttk.Separator(codex_definition_frame, orient='horizontal').grid(row=row_idx, column=0, columnspan=3,
                                                                      sticky='ew', pady=10)
        row_idx += 1
        tk.Label(codex_definition_frame, text="Define Spin Meanings:", fg="#61dafb", bg="black",
                 font=("Arial", 12, "bold")).grid(row=row_idx, column=0, columnspan=3, sticky="w", pady=(0, 5))
        row_idx += 1
        for i, spin_char in enumerate(spins):
            tk.Label(codex_definition_frame, text=f"{spin_char}:", fg="white", bg="black",
                     font=("Arial", 10, "bold")).grid(row=row_idx + i, column=0, sticky="e", padx=5)
            entry = tk.Entry(codex_definition_frame, width=40, bg="#282c34", fg="white", relief=tk.FLAT,
                             insertbackground="white")
            entry.grid(row=row_idx + i, column=1, sticky="ew", pady=2)
            self.spin_codex_entries[spin_char] = entry
        row_idx += len(spins)
        codex_definition_frame.grid_columnconfigure(1, weight=1)
        explanation_frame = tk.Frame(codex_scrollable_frame, bg="black", padx=10, pady=10)
        explanation_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(explanation_frame, text="Compressing Multi-Dimensional Data into Symbolic Representations:",
                 fg="#61dafb", bg="black", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 5))
        self.compression_explanation_text = scrolledtext.ScrolledText(explanation_frame, wrap=tk.WORD, height=15,
                                                                    bg="#1c1e22", fg="white", font=("Arial", 10),
                                                                    relief=tk.FLAT, borderwidth=0)
        self.compression_explanation_text.pack(fill=tk.BOTH, expand=True)
        self.insert_compression_explanation()
        self.compression_explanation_text.config(state=tk.DISABLED)

    def _build_transmission_tab(self):
        transmission_tab_frame = tk.Frame(self.notebook, bg="black")
        self.notebook.add(transmission_tab_frame, text='Toroid Transmission')
        transmission_plots_container = tk.Frame(transmission_tab_frame, bg="black")
        transmission_plots_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.source_toroid_frame = tk.Frame(transmission_plots_container, bg="black", relief=tk.SUNKEN, borderwidth=1)
        self.source_toroid_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(self.source_toroid_frame, text="Source Toroid (Streams Sending)", bg="black", fg="white",
                 font=("Arial", 12, "bold")).pack(pady=2)
        self.fig_trans_source = plt.Figure(figsize=(6, 5), dpi=100, facecolor='black')
        self.ax_trans_source = self.fig_trans_source.add_subplot(111, projection='3d')
        self.canvas_trans_source = FigureCanvasTkAgg(self.fig_trans_source, master=self.source_toroid_frame)
        self.canvas_trans_source.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig_trans_source.tight_layout(pad=0.2)
        self.dest_toroid_frame = tk.Frame(transmission_plots_container, bg="black", relief=tk.SUNKEN, borderwidth=1)
        self.dest_toroid_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(self.dest_toroid_frame, text="Destination Toroid (Nodes Receiving)", bg="black", fg="white",
                 font=("Arial", 12, "bold")).pack(pady=2)
        self.fig_trans_dest = plt.Figure(figsize=(6, 5), dpi=100, facecolor='black')
        self.ax_trans_dest = self.fig_trans_dest.add_subplot(111, projection='3d')
        self.canvas_trans_dest = FigureCanvasTkAgg(self.fig_trans_dest, master=self.dest_toroid_frame)
        self.canvas_trans_dest.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig_trans_dest.tight_layout(pad=0.2)

    def _build_tcp_output_tab(self):
        """Builds the GUI for the TCP/Binary Output tab."""
        tab_frame = tk.Frame(self.notebook, bg="black", padx=10, pady=10)
        self.notebook.add(tab_frame, text='TCP/Binary Output')

        # Top frame for controls and live JSON view
        top_frame = tk.Frame(tab_frame, bg="black")
        top_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        top_frame.grid_columnconfigure(0, weight=1)
        top_frame.grid_rowconfigure(1, weight=1)

        controls_frame = tk.Frame(top_frame, bg="black")
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))
        
        tk.Label(controls_frame, text="Live Frame Output:", fg="#61dafb", bg="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        # Checkbox to switch between JSON and Binary streaming
        binary_check = tk.Checkbutton(controls_frame, text="Stream Binary Data", variable=self.binary_stream_mode,
                                      fg="#FFD700", bg="black", selectcolor="black", activebackground="black",
                                      activeforeground="#FFD700", font=("Arial", 10, "bold"))
        binary_check.pack(side=tk.RIGHT, padx=10)


        self.tcp_output_text = scrolledtext.ScrolledText(top_frame, wrap=tk.NONE, bg="#1c1e22", fg="white",
                                                          font=("Courier New", 10), relief=tk.FLAT, borderwidth=0)
        self.tcp_output_text.grid(row=1, column=0, sticky="nsew")

        # Bottom frame for explanation
        bottom_frame = tk.Frame(tab_frame, bg="black")
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_rowconfigure(0, weight=1)
        
        explanation_text = scrolledtext.ScrolledText(bottom_frame, wrap=tk.WORD, bg="#282c34", fg="white",
                                                      font=("Arial", 10), relief=tk.FLAT, borderwidth=0, height=12)
        explanation_text.pack(fill=tk.BOTH, expand=True)
        self._insert_binary_explanation(explanation_text)
        explanation_text.config(state=tk.DISABLED)

    def _build_mission_tab(self):
        mission_tab_frame = tk.Frame(self.notebook, bg="black", padx=20, pady=20)
        self.notebook.add(mission_tab_frame, text='Target Mission')
        mission_title_label = tk.Label(mission_tab_frame, text="Target Mission:", fg="#61dafb", bg="black",
                                       font=("Arial", 16, "bold"))
        mission_title_label.pack(anchor="w", pady=(0, 10))
        mission_text_content = ("Develop Dynamic Semantic Quantization Algorithms\n\n"
                                "Challenge: Compress 20+ contextual dimensions into sub-100ms inference\n"
                                "while preserving semantic relationships that determine interpretation\n"
                                "accuracy.")
        mission_statement_label = tk.Label(mission_tab_frame, text=mission_text_content, fg="white", bg="#1c1e22",
                                           font=("Arial", 12),
                                           justify=tk.LEFT, wraplength=600, padx=15, pady=15, relief=tk.SOLID,
                                           borderwidth=1)
        mission_statement_label.pack(anchor="nw", fill=tk.X, expand=False)

    def _build_explorer_tab(self):
        explorer_tab_frame = tk.Frame(self.notebook, bg="black", padx=10, pady=10)
        self.notebook.add(explorer_tab_frame, text='Symbolic Explorer')

        explorer_controls_frame = tk.Frame(explorer_tab_frame, bg="black", pady=5)
        explorer_controls_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(explorer_controls_frame, text="Symbol:", fg="white", bg="black", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=(0, 2))
        self.explorer_symbol_menu = ttk.OptionMenu(explorer_controls_frame, self.selected_explorer_symbol, symbols[0],
                                                   *symbols,
                                                   command=lambda _: self._update_explorer_polygon_visualization(),
                                                   style='TMenubutton')
        self.explorer_symbol_menu.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(explorer_controls_frame, text="Color (Hex):", fg="white", bg="black", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=(5, 2))
        self.explorer_color_entry = tk.Entry(explorer_controls_frame, textvariable=self.explorer_color_hex, width=10,
                                             bg="#282c34", fg="white", relief=tk.FLAT, insertbackground="white")
        self.explorer_color_entry.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(explorer_controls_frame, text="Spin:", fg="white", bg="black", font=("Arial", 10)).pack(side=tk.LEFT,
                                                                                                        padx=(5, 2))
        self.explorer_spin_menu = ttk.OptionMenu(explorer_controls_frame, self.selected_explorer_spin, spins[0],
                                                 *spins,
                                                 command=lambda _: self._update_explorer_polygon_visualization(),
                                                 style='TMenubutton')
        self.explorer_spin_menu.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(explorer_controls_frame, text="Sub-Points:", fg="white", bg="black", font=("Arial", 10)).pack(
            side=tk.LEFT, padx=(5, 2))
        self.explorer_sub_points_scale = ttk.Scale(explorer_controls_frame, from_=0, to=5, orient=tk.HORIZONTAL,
                                                   variable=self.explorer_intermediate_points_var, length=100,
                                                   command=lambda _: self._update_explorer_polygon_visualization())
        self.explorer_sub_points_scale.pack(side=tk.LEFT, padx=(0, 5))
        self.explorer_sub_points_label = tk.Label(explorer_controls_frame,
                                                  textvariable=self.explorer_intermediate_points_var,
                                                  fg="white", bg="black", font=("Arial", 10))
        self.explorer_sub_points_label.pack(side=tk.LEFT)

        tk.Button(explorer_controls_frame, text="Update Plot", command=self._update_explorer_polygon_visualization,
                  bg="#61afef", fg="black", padx=10, pady=2, relief=tk.FLAT, font=("Arial", 10, "bold")).pack(
            side=tk.LEFT, padx=(10, 0))

        explorer_content_frame = tk.Frame(explorer_tab_frame, bg="black")
        explorer_content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        explorer_plot_frame = tk.Frame(explorer_content_frame, bg="black", relief=tk.SUNKEN, borderwidth=1)
        explorer_plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.fig_explorer = plt.Figure(figsize=(5, 4), dpi=100, facecolor='black')
        self.ax_explorer = self.fig_explorer.add_subplot(111)
        self.canvas_explorer = FigureCanvasTkAgg(self.fig_explorer, master=explorer_plot_frame)
        self.canvas_explorer.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.fig_explorer.tight_layout(pad=0.5)

        explorer_text_frame = tk.Frame(explorer_content_frame, bg="black")
        explorer_text_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self.explorer_encoding_text = scrolledtext.ScrolledText(explorer_text_frame, wrap=tk.WORD, bg="#1c1e22",
                                                              fg="white", font=("Arial", 10), relief=tk.FLAT,
                                                              borderwidth=0)
        self.explorer_encoding_text.pack(fill=tk.BOTH, expand=True)
        self._insert_explorer_encoding_discussion()

    def _build_quaternion_tab(self):
        quaternion_tab_frame = tk.Frame(self.notebook, bg="black", padx=10, pady=10)
        self.notebook.add(quaternion_tab_frame, text='Quaternion Data')

        quaternion_text = scrolledtext.ScrolledText(quaternion_tab_frame, wrap=tk.WORD, bg="#1c1e22", fg="white",
                                                  font=("Arial", 10), relief=tk.FLAT, borderwidth=0)
        quaternion_text.pack(fill=tk.BOTH, expand=True)
        self._insert_quaternion_explanation(quaternion_text)

    def _build_polygon_analysis_tab(self):
        """Builds the GUI for the Stream Polygon Analysis tab."""
        tab_frame = tk.Frame(self.notebook, bg="black")
        self.notebook.add(tab_frame, text='Stream Polygon Analysis')

        # This main frame will be cleared and rebuilt when num_streams changes
        self.analysis_area_frame = tk.Frame(tab_frame, bg="black")
        self.analysis_area_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _build_falcon_security_tab(self):
        """Builds the GUI for the Falcon Security tab."""
        tab_frame = tk.Frame(self.notebook, bg="black", padx=20, pady=20)
        self.notebook.add(tab_frame, text='Falcon Security')

        # Mission Statement
        tk.Label(tab_frame, text="Falcon Mission Statement", fg="#61dafb", bg="black",
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 10))
        mission_text = (
            "Main elements in Falcon are polynomials of degree n with integer coefficients. The degree n is normally a power of two (typically 512 or 1024). Computations are done modulo a monic polynomial of degree n denoted ϕ (which is always of the form ϕ = x^n + 1).")
        tk.Label(tab_frame, text=mission_text, fg="white", bg="#1c1e22", font=("Arial", 12), justify=tk.LEFT,
                 wraplength=800, padx=15, pady=15, relief=tk.SOLID, borderwidth=1).pack(anchor="w", fill=tk.X,
                                                                                       pady=(0, 20))

        # Explanation Section
        tk.Label(tab_frame, text="Application to Quantum Forward Encryption", fg="#61dafb", bg="black",
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(10, 10))

        explanation_text_widget = scrolledtext.ScrolledText(tab_frame, wrap=tk.WORD, bg="#1c1e22", fg="white",
                                                          font=("Arial", 11), relief=tk.FLAT, borderwidth=0)
        explanation_text_widget.pack(fill=tk.BOTH, expand=True)
        self._insert_falcon_explanation(explanation_text_widget)

    def _build_architecture_tab(self):
        """Builds the GUI for the System Architecture tab."""
        tab_frame = tk.Frame(self.notebook, bg="black", padx=20, pady=20)
        self.notebook.add(tab_frame, text='System Architecture')

        text_widget = scrolledtext.ScrolledText(tab_frame, wrap=tk.WORD, bg="#1c1e22", fg="white",
                                                font=("Arial", 11), relief=tk.FLAT, borderwidth=0)
        text_widget.pack(fill=tk.BOTH, expand=True)
        self._insert_architecture_explanation(text_widget)

    def _build_video_analysis_tab(self):
        tab_frame = tk.Frame(self.notebook, bg="black")
        self.notebook.add(tab_frame, text='Pixel-Semantic Analysis')

        # Main container with two columns
        main_frame = tk.Frame(tab_frame, bg="black")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.grid_columnconfigure(1, weight=1)  # Let the right side expand
        main_frame.grid_rowconfigure(0, weight=1)

        # --- Left Control & Video Panel ---
        left_panel = tk.Frame(main_frame, bg="#282c34", padx=10, pady=10)
        left_panel.grid(row=0, column=0, sticky="ns", padx=(5, 10), pady=5)

        tk.Label(left_panel, text="Video Analysis Controls", fg="white", bg="#282c34",
                 font=("Arial", 12, "bold")).pack(pady=(0, 15))

        self.video_canvas = tk.Canvas(left_panel, width=256, height=256, bg="black", highlightthickness=0)
        self.video_canvas.pack(pady=5)

        # Video controls
        vid_ctrl_frame = tk.Frame(left_panel, bg="#282c34")
        vid_ctrl_frame.pack(fill=tk.X, pady=5)
        tk.Button(vid_ctrl_frame, text="▶", command=self.start_video, bg="#282c34", fg="white",
                  font=("Arial", 12, "bold")).pack(side=tk.LEFT, expand=True)
        tk.Button(vid_ctrl_frame, text="❚❚", command=self.pause_video, bg="#282c34", fg="white",
                  font=("Arial", 12, "bold")).pack(side=tk.LEFT, expand=True)

        self.video_slider = tk.Scale(left_panel, from_=0, to=99, orient=tk.HORIZONTAL,
                                     variable=self.video_frame_index,
                                     command=self.on_video_scroll, bg="#282c34", fg="white", troughcolor="black",
                                     highlightthickness=0)
        self.video_slider.pack(fill=tk.X, pady=5)

        tk.Button(left_panel, text="Load Simulated Video", command=self.load_simulated_video, bg="#61afef",
                  fg="black", padx=10, pady=5).pack(pady=10, fill=tk.X)

        # Semantic Codex
        codex_frame = tk.LabelFrame(left_panel, text="Semantic Codex", fg="white", bg="#282c34", padx=10, pady=10)
        codex_frame.pack(fill=tk.X, pady=20)
        tk.Label(codex_frame, text="Semantic Label -> Polygon Sides", fg="lightgrey", bg="#282c34").pack(anchor='w')
        self.semantic_codex_entries = {}
        for label, sides in self.semantic_codex.items():
            row = tk.Frame(codex_frame, bg="#282c34")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{label}:", fg="white", bg="#282c34").pack(side=tk.LEFT)
            entry = tk.Entry(row, width=4, bg="#1c1e22", fg="white", relief=tk.FLAT)
            entry.insert(0, str(sides))
            entry.pack(side=tk.RIGHT)
            self.semantic_codex_entries[label] = entry
        tk.Button(codex_frame, text="Update Codex", command=self.update_semantic_codex, bg="#98c379",
                  fg="black").pack(pady=10)

        # --- Right Tessellated Toroid Grid Panel ---
        self.tessellated_canvas = tk.Canvas(main_frame, bg="black", highlightthickness=0)
        self.tessellated_canvas.grid(row=0, column=1, sticky="nsew", pady=5, padx=5)

    def _insert_falcon_explanation(self, text_widget):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        explanation = """
--- Core Concept: Lattice-Based Cryptography ---

The Falcon statement describes the mathematical foundation of modern Lattice-Based Cryptography. This is not traditional encryption (like RSA), but a different paradigm built on geometric structures called lattices.

• Polynomial Rings: Instead of working with large prime numbers, we work with large polynomials (e.g., degree 511 or 1023) in a specific algebraic structure called a polynomial ring (e.g., Z[x] / <x^n + 1>). This structure is computationally very efficient.

• The "Hard Problem": Security rests on the assumption that certain problems on these lattices are computationally hard for *both classical and quantum computers*. The most famous is the Shortest Vector Problem (SVP): finding the shortest non-zero vector in a high-dimensional lattice. It's like finding the closest two points in a vast, regularly-spaced grid of points, which becomes exponentially difficult as dimensions increase.

--- Quantum Resistance: Why This Matters ---

Shor's algorithm, a famous quantum computing algorithm, can efficiently break encryption schemes based on prime factorization (like RSA) and discrete logarithms (like ECC). However, Shor's algorithm *does not* solve the hard problems that lattice-based cryptography relies on.

This makes schemes built on these polynomial rings, like Falcon, "quantum-resistant" or "post-quantum". They are designed to remain secure even in an era with powerful quantum computers.

--- Achieving Forward Secrecy ---

Forward Secrecy (or Perfect Forward Secrecy, PFS) is a property of a key-exchange protocol ensuring that if a long-term key is compromised, past session keys remain secure. This prevents an attacker from decrypting previously recorded communications.

It is achieved by generating new, temporary (ephemeral) keys for *every single session*.

--- Synergy: Why Falcon's Math is Ideal for Quantum Forward Encryption ---

While Falcon itself is a digital signature algorithm (for proving identity), its underlying mathematics are the engine for quantum-resistant key exchange, which is necessary for forward secrecy. Here's how they connect:

1.  Efficiency Enables Ephemerality: The core requirement for forward secrecy is generating new keys for each session. The polynomial ring arithmetic described in Falcon's mission statement is extremely fast. This efficiency makes it practical to perform the complex calculations needed to generate a new public/private key pair for every communication session without a noticeable delay. Systems like RSA are too slow to do this practically.

2.  Foundation for Quantum-Resistant KEMs: The same lattice principles are used to build Key Encapsulation Mechanisms (KEMs) like the NIST-standardized CRYSTALS-Kyber. A KEM allows two parties to agree on a shared secret key over an insecure channel.

3.  The Protocol for Quantum Forward Secrecy:
    A. Session Start: Alice and Bob both generate a brand new, ephemeral key pair based on the Falcon-like polynomial mathematics.
    B. Key Exchange: They use a quantum-resistant KEM protocol (like Kyber) to securely establish a shared secret for this session only.
    C. Symmetric Encryption: They use this newly-agreed-upon shared secret to encrypt their actual conversation using a fast symmetric cipher like AES-256.
    D. Session End: Both parties securely erase the ephemeral key pairs they generated in Step A.

Because the ephemeral keys are discarded, even if an attacker later steals a long-term identity key, they cannot go back and decrypt the recorded session traffic. The secret key needed for that specific session is gone forever.

In summary, the mathematics of Falcon provides the **efficient and quantum-resistant building blocks** necessary to create practical key exchange protocols that can be run ephemerally, which is the cornerstone of achieving forward secrecy in a post-quantum world.
"""
        text_widget.insert(tk.END, explanation.strip())
        text_widget.config(state=tk.DISABLED)

    def _insert_architecture_explanation(self, text_widget):
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        explanation = """
--- System Architecture & Symmetrical Scaling ---

This section outlines the principles for scaling the OCTA-13 system and enabling advanced, multi-stream analysis, addressing the goal of symmetrical scaling with 9 data streams.

1.  Modulo-9 Toroidal Symmetry

The current simulation uses 4 streams for visual clarity, but the underlying mathematics are designed to gracefully scale. The ideal configuration, as theorized, is 9 data streams.

• Symmetric Distribution: With 9 streams, the u-coordinate (major circumference) for each stream's origin would be defined as:
  `u_i = i * (2 * π / 9)` for `i` in {0, 1, ..., 8}.
  This places the streams in a perfectly symmetrical configuration around the torus.

• Equidistant & Unbiased: This arrangement ensures that the geometric relationship between any adjacent pair of streams (e.g., Stream 1 to 2, or Stream 5 to 6) is identical. No stream is privileged, which is critical for unbiased relational analysis.

2.  Symmetrical Planar Intersections for Advanced Analysis

The concept of a movable intersecting plane becomes significantly more powerful with 9 symmetrical streams.

• Structured Sampling: Rotating the analysis plane by increments of 40 degrees (360 / 9) would allow an analyst to systematically capture snapshots of stream interactions. For example, one could analyze the state of streams {1, 2, 3}, then rotate the plane to analyze streams {2, 3, 4} with the same relative geometry. This creates a basis for repeatable, controlled experiments.

• Guaranteed Intersections: The concept of "always intersecting at least a certain amount of nodes" is achieved by tuning the plane's offset and threshold relative to the torus's known dimensions (R_TORUS and r_TORUS). The controls can be designed to prevent the plane from moving completely outside the data-rich area, ensuring the analysis windows are always active.

3.  Future Vision: Higher-Order VQ-VAE for Latent Polygons

The "Planar Intersection Analysis" tab is a proof-of-concept for a much more advanced technique.

• Capturing Relational Snapshots: Each time the plane intersects the torus, it doesn't just capture individual symbols. It captures a **set of co-occurring symbols from different streams**. For example, a snapshot might be the vector:
  `{Stream1: (⬢, #FF0000), Stream4: (△, #00FF00), Stream8: (⬤, #FFFFFF)}`

• Training a Higher-Order VQ-VAE: A new, more powerful VQ-VAE would be trained not on the images of individual symbols, but on these high-dimensional relational snapshot vectors.
  - The Encoder would learn to find a compressed representation for these complex multi-stream states.
  - The Codebook would learn a vocabulary of recurring, meaningful *interactions* between streams.

• Latent Polygons: The "latent polygons" would be visualizations of the vectors in this new, higher-order codebook. Each codebook vector (a latent polygon) would represent a fundamental pattern of interaction. For example, one latent polygon might represent the state "Stream A is stable, while Stream B and C are in opposition," a concept far more complex than any single symbol can convey. This allows the system to learn and compress the dynamics of the entire distributed system, not just its individual parts.
"""
        text_widget.insert(tk.END, explanation.strip())
        text_widget.config(state=tk.DISABLED)

    def _insert_quaternion_explanation(self, text_widget):
        """Populates the quaternion explanation text widget with expanded details."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)

        explanation = """
--- Quaternions for the OCTA-13 Protocol ---

Based on the provided PDF, quaternions are a powerful mathematical tool for representing 3D rotations. This has profound implications for the OCTA-13 protocol's goal of compressing high-dimensional data, far surpassing the capability of a simple 'spin' attribute.

1. What is a Quaternion?

A quaternion is a 4D number: q = q₀ + q₁i + q₂j + q₃k
- A 'unit quaternion' (norm = 1) can represent ANY rotation in 3D space.
- It elegantly encodes both the axis of rotation (q₁, q₂, q₃) and the angle of rotation (related to q₀).
- This is vastly more descriptive than a simple 2D spin symbol.

--- How to Encode 20+ Dimensions with Quaternions ---

Encoding 20+ dimensions isn't a one-to-one mapping. It's achieved through a systemic approach combining hierarchical encoding, dynamics, and multi-stream correlation.

A. Hierarchical Encoding (Base Context):
The other symbol attributes provide a broad context, and the quaternion provides fine-grained rotational data within it.
- Shape: The primary category (e.g., 'Object Class').
- Color: The state within that category (e.g., 'Activation Level').
- Quaternion: The precise orientation of that specific state.

B. Sequential Encoding (Dynamics over Time):
A stream of OCTA-13 packets reveals a trajectory. The change between quaternions from one frame to the next (`q_t` to `q_{t+1}`) encodes derivatives.
- Angular Velocity (3 dims): The delta quaternion `Δq = q_{t+1} * q_t⁻¹` represents the rotation between frames. Its axis and angle encode the direction and speed of change.
- Angular Acceleration (3 dims): The change in the delta quaternion over time (`Δq_t` to `Δq_{t+1}`) encodes the acceleration or changing nature of the rotation.

C. Multi-Stream Correlation (The Key to High Dimensions):
This is the most powerful concept. With 4 parallel streams, we analyze the *relationships between them*.
- Relative Rotation: The rotation between any two streams (e.g., Stream A and Stream B) is `q_relative = q_A * q_B⁻¹`. This relative rotation is itself a quaternion, representing 3 degrees of freedom (DoF).
- Combinatorial Explosion of Dimensions: With 4 streams, there are 6 unique pairs of relationships: (A-B), (A-C), (A-D), (B-C), (B-D), (C-D).
- Total Relational Dimensions = 6 pairs * 3 DoF/pair = 18 dimensions.
These 18 dimensions exist *in addition* to the absolute orientation and dynamic properties of each individual stream.

--- Example: Encoding a 21D Human Conversation ---

A system analyzing a person speaking has many data dimensions:
- Head Pose (3D), Gaze (2D), Vocal Prosody (3D), Emotion (3D), Micro-expressions (10D) = 21 Dimensions

The OCTA-13 protocol could encode this as follows:

- Stream 1: "Gross Motor"
  - Shape: `△` (Pose)
  - Quaternion (`q_motor`): Encodes head orientation (3 dims).

- Stream 2: "Focal Point"
  - Shape: `◉` (Attention)
  - Quaternion (`q_gaze`): The *relative* quaternion `q_gaze * q_motor⁻¹` defines gaze direction relative to the head (2 dims).

- Stream 3: "Vocal Dynamics"
  - Shape: `⬡` (Auditory Signal)
  - Quaternion (`q_vocal`): An abstract mapping of Pitch/Cadence/Volume to an orientation in a "vocal space" (3+ dims via dynamics).

- Stream 4: "Facial/Emotional State"
  - Shape: `⬢` (Affective State)
  - Quaternion (`q_emotion`): A "Dynamic Semantic Quantization" algorithm (e.g., a VQ-VAE) learns a mapping from the complex 13D vector of facial muscles + emotion state into a single, representative 3D orientation.

In this model, the system transmits just 4 OCTA-13 packets. The full 21D state is reconstructed by analyzing not only each individual quaternion but also the **six relative quaternions between them**. The relationship `q_vocal * q_emotion⁻¹`, for instance, could represent the complex concept of sarcasm, where vocal tone is misaligned with emotional expression. This is how the protocol can preserve "semantic relationships that determine interpretation accuracy" while achieving massive compression and sub-100ms performance, as quaternion math is highly efficient.
        """
        text_widget.insert(tk.END, explanation.strip())
        text_widget.config(state=tk.DISABLED)  # Make it read-only

    def _insert_binary_explanation(self, text_widget):
        """Populates the explanation for the TCP/Binary output tab."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)
        
        explanation = """
--- Data Stream Output Formats ---

This tab shows a sample of the data being broadcast for each frame. The format can be toggled between human-readable JSON and machine-efficient Binary.

1. JSON Format (Default)
Human-readable, flexible, but verbose. Good for debugging. Each message is a single line of JSON.
- frame: The master clock/synchronization key.
- packets: A list containing one object for each active data stream in that frame.

2. Binary Format (Toggleable)
Extremely compact and fast for machine-to-machine communication. This is crucial for performance-critical systems. The stream is a sequence of binary packets.

--- Proposed Binary Packet Structure for Quaternion Decoders ---

To efficiently transmit data that a downstream agent can use to reconstruct quaternions, we can define a fixed-size binary packet. The key is that the symbols (shape, color, spin) are just *pointers* or *indices*. The decoder will have a corresponding "codex" to look up what these indices mean (e.g., Symbol index 2 maps to a specific base quaternion).

A potential 20-byte packet structure for EACH data point in a stream:

| Field            | Bytes | Type         | Description                                        |
|------------------|-------|--------------|----------------------------------------------------|
| Frame Index      | 4     | Unsigned Int | The master clock (`I`) for sync.                   |
| Stream ID        | 1     | Unsigned Int | Which stream this packet belongs to (`B`).         |
| Symbol Index     | 1     | Unsigned Int | Index into the `symbols` array (`B`).              |
| Color Index      | 1     | Unsigned Int | Index into the `colors` array (`B`).               |
| Spin Index       | 1     | Unsigned Int | Index into the `spins` array (`B`).                |
| U-Coordinate     | 4     | Float        | Toroidal coordinate u (`f`).                       |
| V-Coordinate     | 4     | Float        | Toroidal coordinate v (`f`).                       |
| Status Flags     | 1     | Byte         | Bit 0: Is Overridden. Bits 1-7: Reserved.        |
| Reserved         | 3     | ---          | Padding for alignment and future quaternion data. |
| **Total Size** | **20**|              |                                                    |

struct Format String: `<IBBBBffB3x`

Consideration for Quaternions:
The 3 reserved bytes could be used in a future version. For example, a single byte could encode a "quaternion modifier" index, which the decoder uses to perturb a base quaternion associated with the main symbol. Or, the entire packet structure could be expanded to include four 4-byte floats for a full (w, x, y, z) quaternion, replacing the symbolic indices for a higher-fidelity stream.
"""
        text_widget.insert(tk.END, explanation.strip())
        text_widget.config(state=tk.DISABLED)

    def _update_explorer_polygon_visualization(self):
        """Draws the selected polygon, color, spin, and intermediate points in the explorer tab."""
        ax = self.ax_explorer
        ax.clear()
        ax.set_facecolor("black")

        sym_char = self.selected_explorer_symbol.get()
        color_hex = self.explorer_color_hex.get()
        spin_char = self.selected_explorer_spin.get()
        num_intermediate_pts = self.explorer_intermediate_points_var.get()

        try:
            if not (color_hex.startswith('#') and len(color_hex) == 7): raise ValueError
            int(color_hex[1:], 16)
        except ValueError:
            color_hex = "#CCCCCC"
            self.explorer_color_hex.set(color_hex)

        definition = polygon_definitions.get(sym_char)
        if not definition:
            ax.text(0.5, 0.5, "Symbol not defined", color="red", ha='center', va='center', transform=ax.transAxes)
            self.canvas_explorer.draw()
            return

        radius = 0.8
        poly_patch = None
        face_color_to_use = color_hex if definition.get('fill', True) else 'none'
        edge_color_to_use = color_hex if definition.get('edge_only') else (
            '#BBBBBB' if face_color_to_use != 'none' else color_hex)
        text_color_on_shape = edge_color_to_use if definition.get('edge_only') and not definition.get(
            'fill') else color_hex

        if definition['type'] == 'polygon':
            sides = definition['sides']
            angle_offset = definition.get('rotation_angle', 0)
            angles = np.linspace(0, 2 * np.pi, sides, endpoint=False) + angle_offset
            vertices = np.array([(radius * np.cos(a), radius * np.sin(a)) for a in angles])
            poly_patch = patches.Polygon(vertices, closed=True,
                                         facecolor=face_color_to_use,
                                         edgecolor=edge_color_to_use, linewidth=2)
            ax.add_patch(poly_patch)

            if num_intermediate_pts > 0:
                for i in range(sides):
                    p1 = vertices[i]
                    p2 = vertices[(i + 1) % sides]
                    for j in range(1, num_intermediate_pts + 1):
                        fraction = j / (num_intermediate_pts + 1.0)
                        inter_x = p1[0] + fraction * (p2[0] - p1[0])
                        inter_y = p1[1] + fraction * (p2[1] - p1[1])
                        ax.plot(inter_x, inter_y, 'o', color='skyblue', markersize=5, alpha=0.8, zorder=10)

        elif definition['type'] == 'circle':
            poly_patch = patches.Circle((0, 0), radius,
                                        facecolor=face_color_to_use,
                                        edgecolor=edge_color_to_use, linewidth=2)
            ax.add_patch(poly_patch)
            if definition.get('inner_dot'):
                dot_patch = patches.Circle((0, 0), radius * 0.2, facecolor=edge_color_to_use, edgecolor='none')
                ax.add_patch(dot_patch)
            if num_intermediate_pts > 0:
                num_circle_sub_points = num_intermediate_pts * 8
                sub_angles = np.linspace(0, 2 * np.pi, num_circle_sub_points, endpoint=False)
                for angle in sub_angles:
                    sub_x = radius * np.cos(angle)
                    sub_y = radius * np.sin(angle)
                    ax.plot(sub_x, sub_y, '.', color='skyblue', markersize=3, alpha=0.6, zorder=10)

        ax.text(0, 0, definition['unicode_char'], fontsize=40,
                color=text_color_on_shape,
                ha='center', va='center',
                path_effects=[path_effects.Stroke(linewidth=1.5, foreground='black'), path_effects.Normal()])
        ax.text(0, -radius * 1.25, f"Spin: {spin_char}", fontsize=12, color="lightgray", ha='center', va='top')
        ax.text(0, radius * 1.2, definition['label'], fontsize=12, color="lightgray", ha='center', va='bottom')

        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-1.3, 1.3)
        ax.set_aspect('equal', adjustable='box')
        ax.axis('off')
        self.canvas_explorer.draw()
        self._update_explorer_encoding_discussion_dynamic()

    def _insert_explorer_encoding_discussion(self):
        self.explorer_encoding_text.config(state=tk.NORMAL)
        self.explorer_encoding_text.delete('1.0', tk.END)
        initial_discussion = (
            "The OCTA-13 protocol aims to compress complex, multi-dimensional data (20+ dimensions) "
            "into a compact symbolic representation. This explorer visualizes how three primary attributes "
            "of a symbol – its shape, color, and spin – could contribute to this encoding.\n\n"
            "The goal is to achieve sub-100ms inference while preserving the crucial semantic "
            "relationships that determine interpretation accuracy.\n\n"
            "Select a symbol, color, spin, and number of sub-points above to see how the discussion below adapts "
            "to your choices, illustrating the potential encoding capacity."
        )
        self.explorer_encoding_text.insert(tk.END, initial_discussion)
        self.explorer_encoding_text.config(state=tk.DISABLED)

    def _update_explorer_encoding_discussion_dynamic(self):
        self.explorer_encoding_text.config(state=tk.NORMAL)
        self.explorer_encoding_text.delete('1.0', tk.END)

        sym_char = self.selected_explorer_symbol.get()
        color_hex = self.explorer_color_hex.get()
        spin_char = self.selected_explorer_spin.get()
        num_sub_points = self.explorer_intermediate_points_var.get()
        definition = polygon_definitions.get(sym_char, {})
        shape_label = definition.get('label', 'Unknown Shape')
        num_sides = definition.get('sides', 'N/A') if definition.get('type') == 'polygon' else 'N/A (circle)'

        discussion = f"Selected Symbol: {sym_char} ({shape_label})\n"
        discussion += f"Selected Color: {color_hex}\n"
        discussion += f"Selected Spin: {spin_char}\n"
        discussion += f"Sub-Points Between Vertices: {num_sub_points}\n\n"

        discussion += "--- Conceptual Encoding Potential ---\n\n"

        discussion += f"1. Shape ({shape_label}):\n"
        discussion += f"   The fundamental structure, '{shape_label}', "
        if definition.get('type') == 'polygon':
            discussion += f"with its {num_sides} sides, "
        discussion += "could represent a primary category or a set of core attributes. "
        discussion += "Geometric properties like symmetry, number of vertices, and angles offer distinct 'bins' for coarse-grained features.\n\n"

        discussion += f"2. Sub-Vertex Granularity ({num_sub_points} points between main vertices for polygons):\n"
        discussion += "   Adding points along the edges of polygonal symbols (or on the circumference of circles) introduces a finer level of detail:\n"
        discussion += "   - Increased Resolution: These intermediate points effectively increase the 'resolution' of the shape, allowing for the encoding of more nuanced geometric information or continuous parameters associated with the shape.\n"
        discussion += "   - Relational Encoding: The precise positions of these points (e.g., their distances from the center, from each other, or angles they form) can encode continuous parameters or discrete sub-states related to the primary category defined by the overall shape. For instance, the distribution or density of these points could signify modulation of a feature.\n"
        discussion += "   - Dynamic Forms: In an advanced system, the number or positions of these intermediate points could change dynamically, representing evolving states or modulations of the core semantic concept.\n\n"

        discussion += f"3. Color (currently {color_hex}):\n"
        discussion += "   Color can encode several continuous or discrete sub-dimensions (Hue, Saturation, Value/Lightness) or map to specific learned states.\n\n"

        discussion += f"4. Spin ('{spin_char}'):\n"
        discussion += "   Spin introduces a dynamic, relational, or temporal aspect, signifying trends, rates of change, causality, or interaction types.\n\n"

        discussion += "Combining Dimensions for High-Dimensional Encoding:\n"
        discussion += "The power of this symbolic system lies in the combinatorial capacity. If we have:\n"
        discussion += f"   - S unique shapes (here, {len(polygon_definitions)} base shapes)\n"
        discussion += f"   - G levels of sub-vertex granularity (e.g., {num_sub_points + 1} configurations for polygonal edges)\n"
        discussion += "   - C effective color states (e.g., 300+ from HSV components)\n"
        discussion += f"   - P unique spin states (here, {len(spins)})\n"
        discussion += "The total number of unique symbolic tokens would be S * G * C * P, significantly increasing encoding capacity.\n\n"

        discussion += "To compress 20+ dimensions:\n"
        discussion += "A 'Dynamic Semantic Quantization Algorithm' would learn a mapping (a 'codex') from regions in the 20D+ space to these (Shape, Sub-Vertex State, Color, Spin) tuples. This allows for a richer, more holistic representation of a high-dimensional state, where measurements between the center and these sub-vertex points, or between the points themselves, can encode fine-grained relational data.\n"
        discussion += "   - The 'sub-100ms inference' implies highly optimized quantization and interpretation.\n\n"
        discussion += "This enhanced symbolic representation offers a more granular pointer to complex information."

        self.explorer_encoding_text.insert(tk.END, discussion)
        self.explorer_encoding_text.config(state=tk.DISABLED)

    def insert_compression_explanation(self):
        explanation = """
The OCTA-13 protocol conceptualizes a sophisticated method for handling complex, high-dimensional semantic information by compressing it into a more manageable symbolic form. This approach draws inspiration from several fields and offers unique advantages for tasks requiring rapid interpretation and synchronization of meaning.

Core Concepts:

1.  Symbolic Vector Compression:
    * The Challenge: High-dimensional vectors (e.g., neural network embeddings capturing nuanced meaning) are rich but computationally expensive to process, store, and transmit, especially under tight latency constraints (like sub-100ms). Traditional dimensionality reduction (PCA, t-SNE) can lose interpretive fidelity.
    * The Octa13 Approach:
        * Stage One: Discrete Quantization: Instead of continuous values, the system maps clusters of semantic properties within the high-dimensional space to unique symbols. This is akin to building a "dictionary" where each symbol represents a "concept" or a prototypical region in the semantic manifold. This is philosophically similar to Vector Quantization (VQ) used in signal processing and image compression but adapted for abstract semantic data.
        * Stage Two: Symbolic Recomposition: The compressed representation is a string or sequence of these symbols. A decoder (potentially a context-aware autoencoder) re-expands these symbols back into a high-dimensional representation. The key is that symbols encode meaningful clusters, preserving interpretive accuracy better than naive compression.

2.  Why Symbols?
    * Efficiency: Symbols are discrete and compact, leading to significant data compression.
    * Interpretability (Potential): If the symbolic dictionary is well-constructed, the symbols themselves can carry human-understandable meaning, aiding in debugging and system understanding.
    * Robustness: Discrete symbols can be more robust to noise than continuous values in certain contexts.

Methods for Compressing Multi-Dimensional Data into Symbols:

A. Clustering-Based Approaches (e.g., k-Means as a simple VQ):
    * How it works: High-dimensional data points are grouped into 'k' clusters. Each cluster is then represented by a single symbol (its centroid or an arbitrary label). New data points are mapped to the symbol of the nearest cluster centroid.
    * Pros: Simple to implement, computationally efficient for dictionary creation.
    * Cons: Can be sensitive to initialization, may not capture complex non-linear relationships, information loss can be high if 'k' is too small or clusters are not well-separated.

B. Neural Network-Based Approaches:
    * Vector Quantized Variational Autoencoders (VQ-VAE):
        * How it works: An autoencoder learns to compress input data into a lower-dimensional latent space. However, instead of a continuous latent space, VQ-VAE maps the encoder's output to the closest vector in a learned discrete codebook (the symbolic dictionary). The decoder then reconstructs the input from this quantized vector.
        * Pros: Learns a powerful, data-driven codebook. Can capture complex data distributions. Balances reconstruction fidelity with compression.
        * Cons: More complex to train.
    * Transformers with Quantized Embeddings: Some architectures explore quantizing attention outputs or embeddings directly to reduce model size and latency.

C. Information-Theoretic Approaches:
    * Techniques focusing on minimizing entropy or maximizing mutual information between symbols and the original data dimensions.
    * Often involve more complex mathematical formulations.

D. The Octa13 "Multi-Perspective Inference" & "Distributed Meaning Synchronization" Layers:
    * Beyond simple compression, Octa13 suggests that these symbols are not just static labels but part of a dynamic system.
    * The symbolic representation acts as a "skeleton" that can be perturbed or interpreted in multiple valid ways by the reconstruction module, allowing for diverse inferences without a single ground truth.
    * In a distributed setting, a shared, evolving symbolic dictionary managed by consensus algorithms ensures all nodes maintain a coherent understanding of meaning, even as new information is processed. This is analogous to how language evolves.

Challenges in Symbolic Compression:
    * Dictionary Design & Learning: How to create an optimal set of symbols? How large should it be? Domain-specific or universal? How does it adapt over time?
    * Information Loss vs. Compression: An inherent trade-off. More symbols can mean less loss but also less compression.
    * Context Sensitivity: The meaning of a symbol might change based on surrounding symbols or the broader context. The recomposition stage needs to handle this.
    * "Semantic Gaps": What if a new piece of information doesn't map well to any existing symbol? This necessitates dictionary updates or mechanisms for representing novelty.

The Octa13 symbolic protocol, by integrating these ideas, aims for a system that is not only efficient but also flexible and robust in how it represents and processes meaning, especially in distributed and rapidly evolving environments.
        """
        self.compression_explanation_text.config(state=tk.NORMAL)
        self.compression_explanation_text.insert(tk.END, explanation.strip())
        self.compression_explanation_text.config(state=tk.DISABLED)

    def apply_override(self):
        stream_idx = self.selected_stream_var.get() - 1
        if 0 <= stream_idx < self.num_active_streams:
            self.stream_overrides[stream_idx] = self.override_symbol_var.get()

    def clear_override_for_selected_stream(self):
        stream_idx = self.selected_stream_var.get() - 1
        if 0 <= stream_idx < self.num_active_streams:
            self.stream_overrides[stream_idx] = None

    def clear_all_overrides(self):
        self.stream_overrides = [None] * self.num_active_streams

    def start_animation(self):
        if not self.running:
            self.running = True
            self.advance_frame_loop()

    def pause_animation(self):
        self.running = False

    def reset_simulation_state(self):
        self.running = False
        self.frame_index = 0
        self._initialize_dynamic_structures()
        self._rebuild_stream_gui_elements()
        self.animation_delay_ms.set(300)

        # Reset analysis tab
        for i in range(self.num_active_streams):
            if i < len(self.analysis_canvases):
                self._clear_analysis_canvases(i)

        self.update_torus_plot()
        self.update_stream_panels()
        self.update_packet_data_tab([])
        initial_packets_data = [{'symbol': symbols[0], 'is_overridden': False, 'stream_id': i, 'frame_index': 0} for i
                                 in range(self.num_active_streams)]
        self.update_gaussian_plot(initial_packets_data)
        self.update_transmission_tab_plots()
        self._update_explorer_polygon_visualization()

    def _update_node_flash_timers(self):
        for node in self.destination_transmission_nodes:
            if node['flash_timer'] > 0:
                node['flash_timer'] -= 1

    def _process_direct_stream_transmissions(self):
        for stream_idx, history in enumerate(self.trace_history):
            if not history:
                continue

            head_symbol, head_color, head_spin, head_u, head_v, is_overridden = history[-1]
            symbol_info_to_transmit = (head_symbol, head_color, head_spin)

            if stream_idx < len(self.destination_transmission_nodes):
                dest_node = self.destination_transmission_nodes[stream_idx]
                dest_node['received_symbol_trace'].appendleft(symbol_info_to_transmit)
                dest_node['flash_timer'] = NODE_FLASH_DURATION_FRAMES

    def advance_frame_loop(self):
        if not self.running:
            return

        self.frame_index += 1
        current_frame_packets = []
        self._update_node_flash_timers()

        for i in range(self.num_active_streams):
            override_symbol_str = self.stream_overrides[i]
            is_overridden_flag = override_symbol_str is not None
            u_coord, v_coord = 0, 0

            if is_overridden_flag:
                chosen_symbol_char = override_symbol_str
                try:
                    symbol_idx = symbols.index(chosen_symbol_char)
                except ValueError:
                    symbol_idx = (self.frame_index + i) % ELEMENT_COUNT
                    chosen_symbol_char = symbols[symbol_idx]
                chosen_color_val = colors[symbol_idx % len(colors)]
                chosen_spin_char = spins[symbol_idx % len(spins)]
                initial_u_offset_steps_override = i * (
                            NUM_DISCRETE_U_STEPS // self.num_active_streams if self.num_active_streams > 0 else 0)
                current_u_discrete_step_override = (self.frame_index + initial_u_offset_steps_override) % NUM_DISCRETE_U_STEPS
                u_coord = current_u_discrete_step_override * (2 * np.pi / NUM_DISCRETE_U_STEPS)
                v_coord = (((self.frame_index // ELEMENT_COUNT) * np.pi / 8) + i * (
                            np.pi / self.num_active_streams * 0.5)) % (2 * np.pi)
            else:
                chosen_symbol_char, chosen_color_val, chosen_spin_char, u_coord, v_coord = generate_octa13_packet_data(
                    i, self.frame_index, self.num_active_streams)

            if len(self.trace_history[i]) >= TRACE_LENGTH: self.trace_history[i].pop(0)
            self.trace_history[i].append(
                (chosen_symbol_char, chosen_color_val, chosen_spin_char, u_coord, v_coord, is_overridden_flag))

            packet_info = {'stream_id': i, 'symbol': chosen_symbol_char, 'color': chosen_color_val,
                           'spin': chosen_spin_char,
                           'u_coord': u_coord, 'v_coord': v_coord, 'is_overridden': is_overridden_flag,
                           'frame_index': self.frame_index}
            current_frame_packets.append(packet_info)

        self._process_direct_stream_transmissions()

        # --- Update all visual tabs ---
        self.update_torus_plot()
        self.update_stream_panels()
        self.update_gaussian_plot(current_frame_packets)
        self.update_packet_data_tab(current_frame_packets)

        # Update tabs only if they are potentially visible
        try:
            if self.notebook and self.notebook.winfo_exists():
                current_tab_index = self.notebook.index(self.notebook.select())
                if current_tab_index == 3:  # Toroid Transmission
                    self.update_transmission_tab_plots()
                elif current_tab_index == 4: # TCP/Binary Output
                    self.update_tcp_output_tab(current_frame_packets)
                elif current_tab_index == 8:  # Polygon Analysis
                    self.update_polygon_analysis_tab()

        except (tk.TclError, IndexError):
            pass  # Handle cases where notebook/tab might not exist during shutdown

        # --- Stream the data out ---
        if current_frame_packets:
            if self.binary_stream_mode.get():
                # Create and stream binary data
                binary_packets = b''
                for packet in current_frame_packets:
                    symbol_idx = symbols.index(packet['symbol'])
                    color_idx = colors.index(packet['color'])
                    spin_idx = spins.index(packet['spin'])
                    status_flags = 1 if packet['is_overridden'] else 0
                    
                    # Pack the data into a binary format
                    # < = little-endian, I = unsigned int (4), B = unsigned char (1), f = float (4), x = padding
                    binary_packets += struct.pack('<IBBBBffB3x', 
                                                 packet['frame_index'],
                                                 packet['stream_id'],
                                                 symbol_idx,
                                                 color_idx,
                                                 spin_idx,
                                                 packet['u_coord'],
                                                 packet['v_coord'],
                                                 status_flags)
                if self.stream_mode == 'tcp':
                    self.broadcast_data(binary_packets, is_binary=True)

            else:
                # Stream JSON data
                json_output = json.dumps({'frame': self.frame_index, 'packets': current_frame_packets})
                if self.stream_mode == 'stdout':
                    print(json_output)
                    sys.stdout.flush()
                elif self.stream_mode == 'tcp':
                    self.broadcast_data(json_output, is_binary=False)


        self.root.after(self.animation_delay_ms.get(), self.advance_frame_loop)

    def update_torus_plot(self):
        self.ax_torus.clear()
        elev = 25 + 10 * np.sin(self.frame_index * np.pi / 90)
        azim = (self.frame_index * 2) % 360
        self.ax_torus.view_init(elev=elev, azim=azim)
        u_mesh = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        v_mesh = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        u_mesh, v_mesh = np.meshgrid(u_mesh, v_mesh)
        x_torus, y_torus, z_torus = torus_coords(u_mesh, v_mesh, R_TORUS, r_TORUS)
        self.ax_torus.plot_surface(x_torus, y_torus, z_torus, color="gray", alpha=0.08, rstride=5, cstride=5,
                                   edgecolor='#333333', linewidth=0.2)

        # Draw the dynamic stream polygon
        self._draw_stream_head_polygon(self.ax_torus)

        for i in range(self.num_active_streams):
            for idx, (symbol_char, color_val, spin_char, u_pos, v_pos, is_overridden) in enumerate(
                    self.trace_history[i]):
                x_sym, y_sym, z_sym = torus_coords(u_pos, v_pos, R_TORUS, r_TORUS)
                is_head = (idx == len(self.trace_history[i]) - 1)
                base_size = 40
                size = base_size * 2 if is_head else base_size
                marker_style = '*' if is_overridden else 'o'
                edge_col = 'white' if is_head and is_overridden else ('#cccccc' if is_overridden else 'none')
                if is_overridden: size *= 1.3
                alpha_val = 0.5 + 0.5 * (idx / TRACE_LENGTH) if not is_head else 1.0
                self.ax_torus.scatter(x_sym, y_sym, z_sym, color=color_val, s=size,
                                      marker=marker_style, alpha=alpha_val,
                                      edgecolor=edge_col, linewidth=0.5 if is_head and is_overridden else 0)
                if is_head:
                    self.ax_torus.text(x_sym, y_sym, z_sym + 0.3, symbol_char,
                                       fontsize=12 if is_overridden else 10,
                                       color=color_val, ha='center', va='bottom',
                                       weight='bold' if is_overridden else 'normal')
        self.ax_torus.set_xlim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        self.ax_torus.set_ylim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        self.ax_torus.set_zlim([-r_TORUS - 1, r_TORUS + 1])
        self.ax_torus.axis("off")
        self.canvas_torus_widget.draw()

    def update_stream_panels(self):
        for i in range(self.num_active_streams):
            current_history_len = len(self.trace_history[i])
            for j in range(TRACE_LENGTH):
                if i < len(self.stream_labels_in_panel) and j < len(self.stream_labels_in_panel[i]):
                    if j < current_history_len:
                        sym, col_val, spn, _, _, is_overridden = self.trace_history[i][current_history_len - 1 - j]
                        panel_text = f"{sym}{'(OVR)' if is_overridden else ''} {spn}"
                        self.stream_labels_in_panel[i][j].config(text=panel_text, fg=col_val)
                    else:
                        self.stream_labels_in_panel[i][j].config(text="-", fg="white")

    def update_gaussian_plot(self, current_packets_data):
        self.ax_gaussian.clear()
        X_gauss = np.linspace(-3, 3, 50)
        Y_gauss = np.linspace(-3, 3, 50)
        X_gauss, Y_gauss = np.meshgrid(X_gauss, Y_gauss)
        Z_gauss = np.zeros_like(X_gauss)
        for packet_data in current_packets_data:
            stream_id = packet_data['stream_id']
            is_overridden = packet_data['is_overridden']
            frame_idx = packet_data['frame_index']
            amplitude_multiplier = 1.8 if is_overridden else 1.0
            angle_offset = stream_id * (2 * np.pi / self.num_active_streams) if self.num_active_streams > 0 else 0
            center_x = 1.5 * np.cos(frame_idx * 0.05 + angle_offset)
            center_y = 1.5 * np.sin(frame_idx * 0.05 + angle_offset)
            try:
                symbol_idx = symbols.index(packet_data['symbol'])
                perturb_factor = (symbol_idx - ELEMENT_COUNT / 2) * 0.1
            except ValueError:
                perturb_factor = 0
            sigma = 0.8
            Z_i = amplitude_multiplier * np.exp(-(((X_gauss - (center_x + perturb_factor)) ** 2 / (2 * sigma ** 2)) + \
                                                 ((Y_gauss - (
                                                             center_y - perturb_factor)) ** 2 / (2 * sigma ** 2))))
            Z_gauss += Z_i
        self.ax_gaussian.plot_surface(X_gauss, Y_gauss, Z_gauss, cmap='viridis', alpha=0.9, rstride=1, cstride=1,
                                      edgecolor='none')
        self.ax_gaussian.set_title("Octa13 Symbolic Mix", color='white', fontsize=12)
        self.ax_gaussian.set_facecolor("black")
        self.ax_gaussian.set_zlim(0, self.num_active_streams * 1.5 if self.num_active_streams > 0 else 1.5)
        self.ax_gaussian.axis("off")
        self.canvas_gaussian_widget.draw()

    def update_packet_data_tab(self, current_frame_packets):
        self.packet_data_text.config(state=tk.NORMAL)
        self.packet_data_text.delete('1.0', tk.END)
        if not current_frame_packets:
            self.packet_data_text.insert(tk.END, "No packet data generated yet for this frame.")
        else:
            header = f"Frame: {self.frame_index}\n" + "=" * 40 + "\n"
            self.packet_data_text.insert(tk.END, header)
            for packet in current_frame_packets:
                data_str = (f"Stream ID:      {packet['stream_id'] + 1}\n"
                            f"  Symbol:         {packet['symbol']}\n"
                            f"  Color:          {packet['color']}\n"
                            f"  Spin:           {packet['spin']}\n"
                            f"  U-Coord:        {packet['u_coord']:.4f}\n"
                            f"  V-Coord:        {packet['v_coord']:.4f}\n"
                            f"  Overridden:     {packet['is_overridden']}\n"
                            f"-" * 40 + "\n")
                self.packet_data_text.insert(tk.END, data_str)
        self.packet_data_text.config(state=tk.DISABLED)

    def update_tcp_output_tab(self, current_frame_packets):
        self.tcp_output_text.config(state=tk.NORMAL)
        self.tcp_output_text.delete('1.0', tk.END)
        if not current_frame_packets:
            self.tcp_output_text.insert(tk.END, "No packet data generated for this frame.")
        else:
            if self.binary_stream_mode.get():
                header = f"--- FRAME {self.frame_index}: BINARY STREAM (showing hex representation) ---\n"
                self.tcp_output_text.insert(tk.END, header)
                binary_packets = b''
                for packet in current_frame_packets:
                    symbol_idx = symbols.index(packet['symbol'])
                    color_idx = colors.index(packet['color'])
                    spin_idx = spins.index(packet['spin'])
                    status_flags = 1 if packet['is_overridden'] else 0
                    
                    binary_packets += struct.pack('<IBBBBffB3x', 
                                                 packet['frame_index'], packet['stream_id'],
                                                 symbol_idx, color_idx, spin_idx,
                                                 packet['u_coord'], packet['v_coord'], status_flags)
                # Show hex representation for visualization
                hex_representation = binary_packets.hex(' ')
                self.tcp_output_text.insert(tk.END, hex_representation)
            else:
                header = f"--- FRAME {self.frame_index}: JSON STREAM ---\n"
                self.tcp_output_text.insert(tk.END, header)
                json_output = json.dumps({'frame': self.frame_index, 'packets': current_frame_packets}, indent=2)
                self.tcp_output_text.insert(tk.END, json_output)

        self.tcp_output_text.config(state=tk.DISABLED)

    def _draw_torus_base_and_nodes(self, ax, nodes_list, elev, azim, is_destination_torus=False):
        ax.clear()
        ax.view_init(elev=elev, azim=azim)

        u_mesh = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        v_mesh = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        u_mesh, v_mesh = np.meshgrid(u_mesh, v_mesh)
        x_t, y_t, z_t = torus_coords(u_mesh, v_mesh, R_TORUS, r_TORUS)
        ax.plot_surface(x_t, y_t, z_t, color="gray", alpha=0.08, rstride=5, cstride=5, edgecolor='#333333',
                        linewidth=0.2)

        if is_destination_torus:
            for node_idx, node in enumerate(nodes_list):
                nx, ny, nz = torus_coords(node['u'], node['v'], R_TORUS, r_TORUS)
                node_color_actual = DESTINATION_NODE_COLOR_FLASH if node[
                                                                         'flash_timer'] > 0 else DESTINATION_NODE_COLOR_DEFAULT
                ax.scatter(nx, ny, nz, color=node_color_actual, s=DESTINATION_NODE_SIZE, marker='H',
                           depthshade=True, edgecolors='white', linewidth=0.7)

                trace_list = list(node['received_symbol_trace'])
                for trace_idx, (sym, col, _) in enumerate(trace_list):
                    vertical_offset = 0.3 + trace_idx * 0.25
                    is_most_recent_in_trace = (trace_idx == 0)

                    current_size = 10 if is_most_recent_in_trace else 8
                    current_alpha = 1.0 if is_most_recent_in_trace else 0.7 - (trace_idx * 0.1)
                    ax.text(nx, ny, nz + vertical_offset, sym, fontsize=current_size, color=col,
                            ha='center', va='bottom', weight='bold', alpha=max(0.2, current_alpha))

        ax.set_xlim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        ax.set_ylim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        ax.set_zlim([-r_TORUS - 1, r_TORUS + 1])
        ax.axis("off")

    def update_transmission_tab_plots(self):
        elev = 25 + 10 * np.sin(self.frame_index * np.pi / 120)
        azim_source = (self.frame_index * 1.5) % 360
        azim_dest = (self.frame_index * 1.5 + 10) % 360

        self.ax_trans_source.clear()
        self.ax_trans_source.view_init(elev=elev, azim=azim_source)
        u_mesh_s = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        v_mesh_s = np.linspace(0, 2 * np.pi, NUM_POINTS_TORUS // 2)
        u_mesh_s, v_mesh_s = np.meshgrid(u_mesh_s, v_mesh_s)
        x_ts, y_ts, z_ts = torus_coords(u_mesh_s, v_mesh_s, R_TORUS, r_TORUS)
        self.ax_trans_source.plot_surface(x_ts, y_ts, z_ts, color="gray", alpha=0.08, rstride=5, cstride=5,
                                          edgecolor='#333333', linewidth=0.2)

        for i in range(self.num_active_streams):
            for idx, (symbol_char, color_val, spin_char, u_pos, v_pos, is_overridden) in enumerate(
                    self.trace_history[i]):
                x_sym, y_sym, z_sym = torus_coords(u_pos, v_pos, R_TORUS, r_TORUS)
                is_head = (idx == len(self.trace_history[i]) - 1)

                base_size = 30
                size = base_size * 1.8 if is_head else base_size
                edge_col = 'yellow' if is_head else ('#cccccc' if is_overridden else 'none')
                edge_width = 0.8 if is_head else (0.5 if is_overridden else 0)
                marker_style = '*' if is_overridden else 'o'
                if is_overridden: size *= 1.2

                alpha_val = 0.4 + 0.6 * (idx / TRACE_LENGTH) if not is_head else 1.0
                self.ax_trans_source.scatter(x_sym, y_sym, z_sym, color=color_val, s=size,
                                             marker=marker_style, alpha=alpha_val,
                                             edgecolor=edge_col, linewidth=edge_width)
                if is_head:
                    self.ax_trans_source.text(x_sym, y_sym, z_sym + 0.3, symbol_char,
                                              fontsize=9 if is_overridden else 8,
                                              color=color_val, ha='center', va='bottom', weight='bold')
        self.ax_trans_source.set_xlim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        self.ax_trans_source.set_ylim([-(R_TORUS + r_TORUS) - 1, (R_TORUS + r_TORUS) + 1])
        self.ax_trans_source.set_zlim([-r_TORUS - 1, r_TORUS + 1])
        self.ax_trans_source.axis("off")
        self.canvas_trans_source.draw()

        self._draw_torus_base_and_nodes(self.ax_trans_dest, self.destination_transmission_nodes, elev, azim_dest,
                                        is_destination_torus=True)
        self.canvas_trans_dest.draw()

    # --- Methods for Stream Polygon Analysis ---

    def _draw_stream_head_polygon(self, ax):
        """Draws the polygon formed by the heads of the active streams."""
        if self.frame_index < 1 or self.num_active_streams < 3:
            return

        vertices = []
        for i in range(self.num_active_streams):
            if self.trace_history[i]:
                # Get the head of the trace
                *_, u_pos, v_pos, _ = self.trace_history[i][-1]
                x_sym, y_sym, z_sym = torus_coords(u_pos, v_pos, R_TORUS, r_TORUS)
                vertices.append((x_sym, y_sym, z_sym))

        if len(vertices) >= 3:
            poly = Poly3DCollection([vertices], alpha=0.3, facecolors='cyan')
            ax.add_collection3d(poly)

    def _render_symbol_to_array(self, symbol_char, color_hex, size=32):
        """Renders a symbol into a numpy array image."""
        definition = polygon_definitions.get(symbol_char)
        if not definition: return np.zeros((size, size, 3), dtype=np.uint8)

        img = Image.new('RGB', (size, size), 'black')
        draw = ImageDraw.Draw(img)

        # Draw the symbol on the PIL Image
        radius = size * 0.4
        center = size / 2

        face_color = color_hex if definition.get('fill', True) else None
        edge_color = color_hex

        if definition['type'] == 'polygon':
            sides = definition['sides']
            angle_offset = definition.get('rotation_angle', 0)
            angles = np.linspace(0, 2 * np.pi, sides, endpoint=False) + angle_offset
            vertices = [(center + radius * np.cos(a), center + radius * np.sin(a)) for a in angles]
            draw.polygon(vertices, fill=face_color, outline=edge_color, width=2)
        elif definition['type'] == 'circle':
            bbox = [center - radius, center - radius, center + radius, center + radius]
            draw.ellipse(bbox, fill=face_color, outline=edge_color, width=2)
            if definition.get('inner_dot'):
                dot_radius = radius * 0.2
                dot_bbox = [center - dot_radius, center - dot_radius, center + dot_radius, center + dot_radius]
                draw.ellipse(dot_bbox, fill=edge_color)

        return np.array(img)

    def _conceptual_vq_analysis(self, img_array, model):
        """Simulates VQ-VAE encoding and decoding for an image array."""
        # 1. Encoder (simplified): Average pooling
        h, w, c = img_array.shape
        latent_h, latent_w = model['latent_dim_h'], model['latent_dim_w']
        block_h, block_w = h // latent_h, w // latent_w

        encoded = img_array.reshape(latent_h, block_h, latent_w, block_w, c).mean(axis=(1, 3))

        # 2. Quantizer
        codebook = model['codebook']
        encoded_flat = encoded.reshape(-1, c)
        distances = np.sum((encoded_flat[:, np.newaxis, :] - codebook[np.newaxis, :, :]) ** 2, axis=2)
        indices = np.argmin(distances, axis=1)

        quantized_flat = codebook[indices]
        latent_space_vis = quantized_flat.reshape(latent_h, latent_w, c)

        # 3. Decoder (simplified): Upsampling
        reconstructed = quantized_flat.reshape(latent_h, latent_w, c).repeat(block_h, axis=0).repeat(block_w, axis=1)

        return latent_space_vis.astype(np.uint8), reconstructed.astype(np.uint8)

    def _update_analysis_canvas(self, stream_idx, canvas_title, img_array):
        """Updates a specific canvas in the analysis tab."""
        canvas = self.analysis_canvases[stream_idx][canvas_title]
        img = Image.fromarray(img_array)
        # Use ANTIALIAS for better quality resizing
        img_resized = img.resize((int(canvas.winfo_width()), int(canvas.winfo_height())), Image.Resampling.LANCZOS)
        photo_img = ImageTk.PhotoImage(image=img_resized)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=photo_img)
        canvas.image = photo_img

    def _clear_analysis_canvases(self, stream_idx):
        """Clears all canvases for a given stream's analysis window."""
        for title, canvas in self.analysis_canvases[stream_idx].items():
            canvas.delete("all")
            canvas.create_text(canvas.winfo_width() / 2, canvas.winfo_height() / 2,
                               text="Inactive", fill="grey", font=("Arial", 9))

    def update_polygon_analysis_tab(self):
        """Processes the head of each stream for the analysis windows."""
        for i in range(self.num_active_streams):
            if i < len(self.trace_history) and self.trace_history[i] and i < len(self.analysis_canvases):
                packet_data = self.trace_history[i][-1]  # Get head packet
                symbol_char, color_val, *_ = packet_data

                # Render symbol to an image array
                symbol_img = self._render_symbol_to_array(symbol_char, color_val)
                self._update_analysis_canvas(i, "Vertex Symbol", symbol_img)

                # Run conceptual VQ-VAE
                latent_img, reconstructed_img = self._conceptual_vq_analysis(symbol_img, self.analysis_vq_models[i])

                # Update latent and reconstructed canvases
                self._update_analysis_canvas(i, "Latent Space (VQ)", latent_img)
                self._update_analysis_canvas(i, "Reconstructed", reconstructed_img)
            else:
                if i < len(self.analysis_canvases):
                    self._clear_analysis_canvases(i)

    # --- Video Analysis Methods ---

    def load_simulated_video(self, num_frames=100, width=256, height=256):
        """Generates a simple video of a moving shape."""
        self.video_frames = []
        for i in range(num_frames):
            img = Image.new('RGB', (width, height), 'black')
            draw = ImageDraw.Draw(img)

            # Object moving in a circle
            angle = (i / num_frames) * 2 * math.pi
            center_x = width / 2 + (width / 4) * math.cos(angle)
            center_y = height / 2 + (height / 4) * math.sin(angle)
            size = 20

            draw.ellipse([center_x - size, center_y - size, center_x + size, center_y + size], fill='skyblue',
                         outline='white')

            self.video_frames.append(np.array(img))

        self.video_frame_index.set(0)
        self.video_slider.config(to=num_frames - 1)
        self._update_video_display(0)

    def start_video(self):
        if not self.video_running and self.video_frames:
            self.video_running = True
            self._animate_video()

    def pause_video(self):
        self.video_running = False

    def on_video_scroll(self, value_str):
        self.pause_video()
        idx = int(value_str)
        self._update_video_display(idx)

    def _animate_video(self):
        if not self.video_running:
            return

        current_idx = self.video_frame_index.get()
        next_idx = (current_idx + 1) % len(self.video_frames)
        self.video_frame_index.set(next_idx)
        self._update_video_display(next_idx)

        self.root.after(50, self._animate_video)  # approx 20 FPS

    def _update_video_display(self, idx):
        if not self.video_frames:
            return

        frame_data = self.video_frames[idx]
        img = Image.fromarray(frame_data)
        photo = ImageTk.PhotoImage(image=img)

        self.video_canvas.delete("all")
        self.video_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.video_canvas.image = photo

        self._analyze_and_draw_tessellation(idx)

    def update_semantic_codex(self):
        for label, entry in self.semantic_codex_entries.items():
            try:
                self.semantic_codex[label] = int(entry.get())
            except ValueError:
                pass  # Ignore invalid non-integer input
        self._analyze_and_draw_tessellation(self.video_frame_index.get())

    def _analyze_and_draw_tessellation(self, frame_idx):
        if not self.video_frames or frame_idx < 1:
            self.tessellated_canvas.delete("all")
            return

        current_frame = self.video_frames[frame_idx].astype(np.float32)
        prev_frame = self.video_frames[frame_idx - 1].astype(np.float32)

        # Calculate pixel-wise difference (a simple motion detection)
        diff = np.mean(np.abs(current_frame - prev_frame), axis=2)

        # Normalize motion map
        max_diff = diff.max()
        if max_diff > 0:
            diff /= max_diff

        # Get canvas size for drawing
        canvas_w = self.tessellated_canvas.winfo_width()
        canvas_h = self.tessellated_canvas.winfo_height()
        self.tessellated_canvas.delete("all")

        grid_size = 16  # Draw a 16x16 grid of toroids/symbols
        if canvas_w == 1 or canvas_h == 1:  # Canvas not ready
            return

        cell_w = canvas_w / grid_size
        cell_h = canvas_h / grid_size

        for y in range(grid_size):
            for x in range(grid_size):
                # Sample a region from the difference map
                px_y = int((y / grid_size) * diff.shape[0])
                px_x = int((x / grid_size) * diff.shape[1])
                motion_val = diff[px_y, px_x]

                # Use codex to map motion to symbol sides
                if motion_val > 0.5:
                    sides = self.semantic_codex["High Motion"]
                    color = "#FF4136"  # Red
                elif motion_val > 0.1:
                    sides = self.semantic_codex["Medium Motion"]
                    color = "#FFDC00"  # Yellow
                else:
                    sides = self.semantic_codex["Low Motion"]
                    color = "#0074D9"  # Blue

                # Draw the corresponding polygon
                center_x, center_y = (x + 0.5) * cell_w, (y + 0.5) * cell_h
                radius = min(cell_w, cell_h) * 0.4

                angle_step = 2 * math.pi / sides if sides > 0 else 0
                start_angle = -math.pi / 2

                vertices = []
                if sides > 2:
                    for i in range(sides):
                        angle = start_angle + i * angle_step
                        vx = center_x + radius * math.cos(angle)
                        vy = center_y + radius * math.sin(angle)
                        vertices.append((vx, vy))
                    self.tessellated_canvas.create_polygon(vertices, fill=color, outline='gray20')
                elif sides == 2:  # line
                    self.tessellated_canvas.create_line(center_x - radius, center_y, center_x + radius, center_y,
                                                        fill=color, width=2)
                else:  # dot
                    self.tessellated_canvas.create_oval(center_x - 2, center_y - 2, center_x + 2, center_y + 2,
                                                        fill=color, outline='')
    
    # --- TCP Server Methods for Data Streaming ---
    def start_tcp_server(self, host, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            print(f"[TCP Server] Listening for connections on {host}:{port}")
            thread = threading.Thread(target=self.accept_clients, daemon=True)
            thread.start()
        except OSError as e:
            print(f"[TCP Server] Error starting server: {e}")
            self.stream_mode = None # Disable streaming if server fails

    def accept_clients(self):
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"[TCP Server] Accepted connection from {addr}")
                with self.lock:
                    self.client_sockets.append(client_socket)
            except OSError:
                break # Socket was likely closed

    def broadcast_data(self, data, is_binary=False):
        with self.lock:
            dead_sockets = []
            
            # For JSON, append a newline. For binary, the structure is fixed-size, so no delimiter is needed.
            message = data if is_binary else data.encode('utf-8') + b'\n'

            for client_socket in self.client_sockets:
                try:
                    client_socket.sendall(message)
                except (socket.error, BrokenPipeError):
                    dead_sockets.append(client_socket)
            
            for dead in dead_sockets:
                print("[TCP Server] Client disconnected.")
                self.client_sockets.remove(dead)

    def shutdown_server(self):
        if self.stream_mode == 'tcp' and self.server_socket:
            print("[TCP Server] Shutting down.")
            with self.lock:
                for client in self.client_sockets:
                    client.close()
            self.server_socket.close()

    def on_closing(self):
        self.shutdown_server()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    # To run with TCP streaming (default):
    app = OCTA13Visualizer(root, stream_mode='tcp', host='localhost', port=9999)
    # To run with stdout streaming, change the line above to:
    # app = OCTA13Visualizer(root, stream_mode='stdout')
    root.mainloop()
