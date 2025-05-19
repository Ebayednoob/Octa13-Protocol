import tkinter as tk
from tkinter import ttk, scrolledtext, PanedWindow
from collections import deque
import math
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from typing import Dict, List, Tuple, Optional, Deque, Any

# --- Constants ---
PHI = (1 + math.sqrt(5)) / 2  # Golden ratio
SPIRAL_CACHE_MAXLEN = 13      # Max length for the spiral cache visualization cycle
PLOT_CYCLE_LENGTH = 12        # Used for Z-coordinate in spiral calculation

# Bit slicing indices for the 13-bit packet
OCT_START, OCT_END = 0, 3
NOD_START, NOD_END = 3, 6
POS_START, POS_END = 6, 9
CHK_START, CHK_END = 9, 12
END_BIT_INDEX = 12
PACKET_LENGTH = 13

# Base Semantic Maps for Sigil Fields
# These are used for manual selection dropdowns and for codex generation.
OCT_MAP: Dict[str, str] = {
    "Root": "000",
    "Octave+1": "001",
    "Octave+2": "010",
    "Minor Third": "011",
    "Perfect Fifth": "100",
    "Octave-1": "101",
    "Quantum Fold": "110", 
    "Broadcast": "111",   
}

NOD_MAP: Dict[str, str] = {
    "Tetrahedron": "000",
    "Cube": "001",
    "Octahedron": "010",
    "Dodecahedron": "011",
    "Icosahedron": "100",
    "Null": "101",
    "Tritone": "110",
    "Harmonic Sync": "111",
}

POS_MAP: Dict[str, str] = {
    "Anchor": "000",
    "Direction": "001",
    "Recurse Start": "010",
    "Recurse Stop": "011",
    "Fold Entry": "100",
    "Fold Exit": "101",
    "Triadic Align": "110",
    "Instruction": "111",
}

# Checksum function: XOR of Octave, Node, and Position bits
CHK_FUNC = lambda oct_str, nod_str, pos_str: format(
    (int(oct_str, 2) ^ int(nod_str, 2) ^ int(pos_str, 2)), '03b'
)

# --- Codex Generation ---
CHAR_TO_SIGIL_SPEC_CODEX: Dict[str, Tuple[str, str, str]] = {} # Char -> (Oct_Name, Nod_Name, Pos_Name)
SIGIL_SPEC_TO_CHAR_CODEX: Dict[Tuple[str, str, str], str] = {} # (Oct_Bits, Nod_Bits, Pos_Bits) -> Char

def generate_default_codex():
    """Generates the default codex mapping printable ASCII characters to sigil specifications."""
    characters = "".join(chr(i) for i in range(32, 127)) # Printable ASCII

    # Use first 6 Octave options for the codex base, as per original request
    oct_options_for_codex = list(OCT_MAP.keys())[:6] 
    nod_options_for_codex = list(NOD_MAP.keys())
    pos_options_for_codex = list(POS_MAP.keys())

    char_idx = 0
    # Iterate to create unique combinations for each character
    for pos_name in pos_options_for_codex:
        if char_idx >= len(characters): break
        for oct_name in oct_options_for_codex:
            if char_idx >= len(characters): break
            for nod_name in nod_options_for_codex:
                if char_idx >= len(characters): break
                
                char = characters[char_idx]
                # Store semantic names for encoding text to sigil
                CHAR_TO_SIGIL_SPEC_CODEX[char] = (oct_name, nod_name, pos_name)

                # Store binary parts for decoding sigil to text (more robust key)
                oct_bits = OCT_MAP[oct_name]
                nod_bits = NOD_MAP[nod_name]
                pos_bits = POS_MAP[pos_name]
                SIGIL_SPEC_TO_CHAR_CODEX[(oct_bits, nod_bits, pos_bits)] = char
                
                char_idx += 1
    
    if char_idx < len(characters):
        print(f"Warning: Default Codex only mapped {char_idx} out of {len(characters)} printable ASCII characters.")

generate_default_codex() # Populate the codex dictionaries at startup

# --- Data Structures for Visualization ---
class SpiralCacheEntry(dict):
    packet_str: str; coords: Tuple[float, float, float]; original_xyz_int: Tuple[int, int, int]
    chk_int: int; end_bool: bool; index: int

spiral_cache: Deque[SpiralCacheEntry] = deque(maxlen=SPIRAL_CACHE_MAXLEN)

# --- Sigil Packet Logic ---
class SigilPacket:
    def __init__(self, oct_bits: str, nod_bits: str, pos_bits: str, chk_bits: str, end_bit: str):
        self.oct_bits: str = oct_bits
        self.nod_bits: str = nod_bits
        self.pos_bits: str = pos_bits
        self.chk_bits: str = chk_bits
        self.end_bit: str = end_bit 
        self.is_valid_checksum: bool = self._validate_checksum()

    def _validate_checksum(self) -> bool:
        expected_chk = CHK_FUNC(self.oct_bits, self.nod_bits, self.pos_bits)
        return self.chk_bits == expected_chk

    def as_string(self) -> str:
        return f"{self.oct_bits}{self.nod_bits}{self.pos_bits}{self.chk_bits}{self.end_bit}"

    @classmethod
    def from_string(cls, packet_str: str) -> Optional['SigilPacket']:
        if len(packet_str) != PACKET_LENGTH or not all(c in "01" for c in packet_str):
            return None
        return cls(
            packet_str[OCT_START:OCT_END], packet_str[NOD_START:NOD_END],
            packet_str[POS_START:POS_END], packet_str[CHK_START:CHK_END],
            packet_str[END_BIT_INDEX]
        )

    @classmethod
    def from_semantic_values(cls, oct_name: str, nod_name: str, pos_name: str, end_value: int) -> 'SigilPacket':
        oct_bits = OCT_MAP[oct_name]
        nod_bits = NOD_MAP[nod_name]
        pos_bits = POS_MAP[pos_name]
        chk_bits = CHK_FUNC(oct_bits, nod_bits, pos_bits)
        end_bit_str = str(end_value)
        return cls(oct_bits, nod_bits, pos_bits, chk_bits, end_bit_str)

    def get_semantic_breakdown(self) -> str:
        """Returns a string with the semantic breakdown of the packet."""
        oct_name, nod_name, pos_name = self.get_semantic_names()
        checksum_status = "Valid" if self.is_valid_checksum else f"Invalid (Expected: {CHK_FUNC(self.oct_bits, self.nod_bits, self.pos_bits)})"
        return (
            f"Octave Sel.: {oct_name} ({self.oct_bits})\n"
            f"Node Type:   {nod_name} ({self.nod_bits})\n"
            f"Position/Fn: {pos_name} ({self.pos_bits})\n"
            f"Checksum:    {self.chk_bits} -> {checksum_status}\n"
            f"END Bit:     {self.end_bit} ({'Closed' if self.end_bit == '1' else 'Open'})"
        )

    def get_semantic_names(self) -> Tuple[str, str, str]:
        oct_name = next((k for k, v in OCT_MAP.items() if v == self.oct_bits), f"UnknownOct({self.oct_bits})")
        nod_name = next((k for k, v in NOD_MAP.items() if v == self.nod_bits), f"UnknownNod({self.nod_bits})")
        pos_name = next((k for k, v in POS_MAP.items() if v == self.pos_bits), f"UnknownPos({self.pos_bits})")
        return oct_name, nod_name, pos_name

# --- Visualization Helper Functions ---
def compute_phi_spiral_coordinates(index: int, cycle_len: int = PLOT_CYCLE_LENGTH) -> Tuple[float, float, float]:
    theta_degrees = 137.5 * index 
    theta_radians = math.radians(theta_degrees)
    r = math.sqrt(index + 1) 
    z = index // cycle_len 
    return r * math.cos(theta_radians), r * math.sin(theta_radians), z

def update_global_spiral_cache(packet_obj: SigilPacket, current_vis_index: int) -> SpiralCacheEntry:
    entry: SpiralCacheEntry = {
        "packet_str": packet_obj.as_string(),
        "coords": compute_phi_spiral_coordinates(current_vis_index),
        "original_xyz_int": (int(packet_obj.oct_bits,2), int(packet_obj.nod_bits,2), int(packet_obj.pos_bits,2)),
        "chk_int": int(packet_obj.chk_bits, 2),
        "end_bool": packet_obj.end_bit == '1',
        "index": current_vis_index 
    }
    spiral_cache.append(entry)
    return entry

def get_spiral_plot_data(current_vis_frame_count: int) -> Tuple[Optional[SpiralCacheEntry], Optional[SpiralCacheEntry], List[Tuple[float, float, float]]]:
    if not spiral_cache: return None, None, []
    current = spiral_cache[-1]
    prior = spiral_cache[-2] if (current_vis_frame_count % 2 == 0) and (len(spiral_cache) > 1) else None
    return prior, current, [e["coords"] for e in spiral_cache]

# --- Tkinter Application ---
class Octa13EncoderDecoderApp:
    def __init__(self, root_tk: tk.Tk):
        self.root = root_tk
        self.root.title("Ebayednoob - OCTA-13 Text & Sigil Interface (Codex v1.1)")
        self.root.geometry("1450x1050") 
        self.root.configure(bg="black")

        self.visualization_frame_counter: int = 0
        self.current_codex_name = tk.StringVar(value="Default Codex")
        
        # UI Variables for manual sigil encoding
        self.manual_oct_var = tk.StringVar(value=list(OCT_MAP.keys())[0])
        self.manual_nod_var = tk.StringVar(value=list(NOD_MAP.keys())[0])
        self.manual_pos_var = tk.StringVar(value=list(POS_MAP.keys())[0])
        self.end_bit_var = tk.IntVar(value=0) # For "Set END Bit to 1"

        self._setup_styles()
        self._build_header()
        self._build_control_panel()
        self._build_io_panel()
        self._build_visualization_canvas()
        self._initial_plot_update()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam') 
        style.configure("TCombobox", fieldbackground="black", background="grey20", foreground="#00FF00", arrowcolor="#00FF00", bordercolor="grey40", padding=(3,3))
        style.map('TCombobox', fieldbackground=[('readonly','black')], selectbackground=[('readonly', 'black')], selectforeground=[('readonly', '#00FF00')])
        style.configure("TButton", background="grey20", foreground="#00FF00", font=("Courier", 10, "bold"), relief=tk.RAISED, borderwidth=1, padding=5)
        style.map("TButton", background=[('active', 'grey30')], relief=[('pressed', tk.SUNKEN)])
        style.configure("Control.TButton", foreground="yellow") # For Clear All button

    def _build_header(self):
        # ... (header remains the same)
        header_frame = tk.Frame(self.root, bg="black")
        header_frame.pack(pady=(10,0), fill=tk.X)
        tk.Label(header_frame, text="E B A Y E D N O O B", font=("Courier", 28, "bold"), fg="#00FF00", bg="black").pack()
        tk.Label(header_frame, text="OCTA-13 TEXT & SIGIL INTERFACE (Codex Enabled)", font=("Courier", 16), fg="#00FF00", bg="black").pack(pady=(0,5))

    def _build_control_panel(self):
        panel_outer = tk.Frame(self.root, bg="black")
        panel_outer.pack(fill=tk.X, padx=10, pady=5)

        # Top row for Codex, Text Encode/Decode, Clear
        top_controls = tk.Frame(panel_outer, bg="black")
        top_controls.pack(fill=tk.X, pady=(0,5))

        tk.Label(top_controls, text="Codex:", bg="black", fg="white", font=("Courier", 10)).pack(side=tk.LEFT, padx=(0,0))
        ttk.Combobox(top_controls, textvariable=self.current_codex_name, values=["Default Codex"], state="readonly", font=("Courier", 9), width=13).pack(side=tk.LEFT, padx=(2,10))
        
        ttk.Button(top_controls, text="Encode Text", command=self._on_encode_text_button).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_controls, text="Decode Sigil(s) from Output", command=self._on_decode_sigils_from_output_button).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_controls, text="Clear All", command=self._on_clear_all_button, style="Control.TButton").pack(side=tk.LEFT, padx=3)

        # Bottom row for Manual Sigil Encoding
        manual_controls = tk.Frame(panel_outer, bg="black")
        manual_controls.pack(fill=tk.X, pady=(5,0))

        tk.Label(manual_controls, text="Manual Sigil:", bg="black", fg="white", font=("Courier", 10)).pack(side=tk.LEFT, padx=(0,5))
        self._add_manual_dropdown(manual_controls, "Oct:", self.manual_oct_var, list(OCT_MAP.keys()))
        self._add_manual_dropdown(manual_controls, "Nod:", self.manual_nod_var, list(NOD_MAP.keys()))
        self._add_manual_dropdown(manual_controls, "Pos:", self.manual_pos_var, list(POS_MAP.keys()))
        
        tk.Checkbutton(
            manual_controls, text="Set END Bit to 1 (Closed)", variable=self.end_bit_var,
            bg="black", fg="#00FF00", selectcolor="black", activebackground="black", activeforeground="#00FF00",
            font=("Courier", 9), pady=0, padx=0
        ).pack(side=tk.LEFT, padx=(10,5), anchor='center')

        ttk.Button(manual_controls, text="Encode Selected Sigil", command=self._on_encode_selected_sigil_button).pack(side=tk.LEFT, padx=5)
        
    def _add_manual_dropdown(self, parent: tk.Frame, label_text: str, variable: tk.StringVar, options: List[str]):
        tk.Label(parent, text=label_text, bg="black", fg="white", font=("Courier", 9)).pack(side=tk.LEFT)
        ttk.Combobox(parent, textvariable=variable, values=options, state="readonly", font=("Courier", 9), width=max(len(o) for o in options)//2 + 5).pack(side=tk.LEFT, padx=(2,5))


    def _build_io_panel(self):
        # ... (io_panel remains the same)
        io_pane = PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg="grey10", sashwidth=6)
        io_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # Input Frame (Left)
        input_frame = tk.Frame(io_pane, bg="black", padx=5, pady=5)
        tk.Label(input_frame, text="Input Text (for Encoding) / Decoded Info", bg="black", fg="white", font=("Courier", 11)).pack(anchor="w")
        self.input_text_area = scrolledtext.ScrolledText(input_frame, height=10, width=60, font=("Courier", 11), bg="grey15", fg="#E0E0E0", insertbackground="white", relief=tk.SOLID, borderwidth=1)
        self.input_text_area.pack(fill=tk.BOTH, expand=True)
        io_pane.add(input_frame, stretch="always")
        # Output Frame (Right)
        output_frame = tk.Frame(io_pane, bg="black", padx=5, pady=5)
        tk.Label(output_frame, text="Encoded Sigils / Input Sigils (for Decoding)", bg="black", fg="white", font=("Courier", 11)).pack(anchor="w")
        self.output_sigils_area = scrolledtext.ScrolledText(output_frame, height=10, width=60, font=("Courier", 11), bg="grey15", fg="#00FF00", insertbackground="#00FF00", relief=tk.SOLID, borderwidth=1)
        self.output_sigils_area.pack(fill=tk.BOTH, expand=True)
        io_pane.add(output_frame, stretch="always")


    def _build_visualization_canvas(self):
        # ... (visualization_canvas remains the same)
        vis_frame = tk.Frame(self.root, bg="black", pady=5)
        vis_frame.pack(fill=tk.BOTH, expand=True)
        self.figure = plt.Figure(figsize=(16, 4.2), dpi=90) 
        self.figure.patch.set_facecolor('black')
        self.ax1_prior = self.figure.add_subplot(131, projection='3d')
        self.ax2_current = self.figure.add_subplot(132, projection='3d')
        self.ax3_spiral = self.figure.add_subplot(133, projection='3d')
        self.canvas = FigureCanvasTkAgg(self.figure, master=vis_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)
        for ax_item in [self.ax1_prior, self.ax2_current, self.ax3_spiral]:
            ax_item.set_facecolor('black'); ax_item.tick_params(colors='grey', labelsize=7)
            ax_item.xaxis.label.set_color('grey'); ax_item.yaxis.label.set_color('grey'); ax_item.zaxis.label.set_color('grey')
            ax_item.title.set_color('lightgrey'); ax_item.grid(False)
            ax_item.xaxis.set_pane_color((0.0,0.0,0.0,1)); ax_item.yaxis.set_pane_color((0.0,0.0,0.0,1)); ax_item.zaxis.set_pane_color((0.0,0.0,0.0,1))

    def _reset_visualization_state(self):
        spiral_cache.clear()
        self.visualization_frame_counter = 0
        self._initial_plot_update()

    def _on_encode_text_button(self):
        self._reset_visualization_state()
        input_text = self.input_text_area.get("1.0", tk.END).strip()
        if not input_text:
            self.output_sigils_area.delete("1.0", tk.END); self.output_sigils_area.insert(tk.END, "Error: Input text is empty.")
            return

        generated_sigils: List[str] = []
        final_end_bit = self.end_bit_var.get() # Use the general END bit checkbox

        for i, char_to_encode in enumerate(input_text):
            sigil_spec = CHAR_TO_SIGIL_SPEC_CODEX.get(char_to_encode)
            if sigil_spec:
                oct_name, nod_name, pos_name = sigil_spec
                current_end_bit = final_end_bit if i == len(input_text) - 1 else 0
                packet = SigilPacket.from_semantic_values(oct_name, nod_name, pos_name, current_end_bit)
                generated_sigils.append(packet.as_string())
                self.visualization_frame_counter +=1
                update_global_spiral_cache(packet, self.visualization_frame_counter -1)
                self._update_plot_iterative()
            else:
                generated_sigils.append(f"[ERR:NoCodex:'{char_to_encode}']")
        
        self.output_sigils_area.delete("1.0", tk.END)
        self.output_sigils_area.insert(tk.END, "\n".join(generated_sigils))

    def _on_encode_selected_sigil_button(self):
        self._reset_visualization_state()
        oct_name = self.manual_oct_var.get()
        nod_name = self.manual_nod_var.get()
        pos_name = self.manual_pos_var.get()
        end_val = self.end_bit_var.get()

        packet = SigilPacket.from_semantic_values(oct_name, nod_name, pos_name, end_val)
        
        self.output_sigils_area.delete("1.0", tk.END)
        self.output_sigils_area.insert(tk.END, packet.as_string())

        self.input_text_area.delete("1.0", tk.END)
        self.input_text_area.insert(tk.END", "Manually Encoded Sigil Details:\n-----------------------------\n")
        self.input_text_area.insert(tk.END, packet.get_semantic_breakdown())
        
        self.visualization_frame_counter +=1
        update_global_spiral_cache(packet, self.visualization_frame_counter -1)
        self._update_plot()


    def _on_decode_sigils_from_output_button(self):
        self._reset_visualization_state()
        sigil_stream_text = self.output_sigils_area.get("1.0", tk.END).strip()
        if not sigil_stream_text:
            self.input_text_area.delete("1.0", tk.END); self.input_text_area.insert(tk.END, "Error: Sigil input area is empty.")
            return

        sigil_lines = [line.strip() for line in sigil_stream_text.splitlines() if line.strip()]
        decoded_info_parts: List[str] = []

        if len(sigil_lines) == 1 and len(sigil_lines[0]) == PACKET_LENGTH and all(c in "01" for c in sigil_lines[0]):
            # Single sigil: show breakdown and codex char if exists
            packet = SigilPacket.from_string(sigil_lines[0])
            if packet:
                decoded_info_parts.append("Decoded Sigil Details:\n----------------------")
                decoded_info_parts.append(packet.get_semantic_breakdown())
                key_tuple = (packet.oct_bits, packet.nod_bits, packet.pos_bits)
                char = SIGIL_SPEC_TO_CHAR_CODEX.get(key_tuple)
                if char:
                    decoded_info_parts.append(f"\nCodex Character: '{char}'")
                else:
                    decoded_info_parts.append("\n(No direct match in current text codex)")
                self.visualization_frame_counter +=1
                update_global_spiral_cache(packet, self.visualization_frame_counter-1)
        else: # Multiple sigils or invalid format for single detailed view
            decoded_chars_list: List[str] = []
            for sigil_str in sigil_lines:
                if len(sigil_str) == PACKET_LENGTH and all(c in "01" for c in sigil_str):
                    packet = SigilPacket.from_string(sigil_str)
                    if packet:
                        key_tuple = (packet.oct_bits, packet.nod_bits, packet.pos_bits)
                        char = SIGIL_SPEC_TO_CHAR_CODEX.get(key_tuple)
                        decoded_chars_list.append(char if char else f"[?{packet.oct_bits}{packet.nod_bits}{packet.pos_bits}?]")
                        self.visualization_frame_counter +=1
                        update_global_spiral_cache(packet, self.visualization_frame_counter-1)
                    else: decoded_chars_list.append(f"[ERR:Parse:'{sigil_str}']")
                elif sigil_str.startswith("[ERR:NoCodex:") or not sigil_str : 
                    if sigil_str: decoded_chars_list.append(sigil_str) 
                else: decoded_chars_list.append(f"[ERR:Format:'{sigil_str}']")
            decoded_info_parts.append("Decoded Text Stream:\n--------------------\n" + "".join(decoded_chars_list))

        self.input_text_area.delete("1.0", tk.END)
        self.input_text_area.insert(tk.END, "\n".join(decoded_info_parts))
        self._update_plot()


    def _on_clear_all_button(self):
        self.input_text_area.delete("1.0", tk.END)
        self.output_sigils_area.delete("1.0", tk.END)
        self._reset_visualization_state()

    def _initial_plot_update(self):
        # ... (initial_plot_update remains mostly the same)
        self.ax1_prior.clear(); self.ax2_current.clear(); self.ax3_spiral.clear()
        self.ax1_prior.set_title("Prior (P)", fontsize=9); self.ax2_current.set_title("Current (C)", fontsize=9)
        self.ax3_spiral.set_title(f"Sigil Spiral (Max {SPIRAL_CACHE_MAXLEN})", fontsize=9)
        max_r = math.sqrt(SPIRAL_CACHE_MAXLEN); max_z = SPIRAL_CACHE_MAXLEN // PLOT_CYCLE_LENGTH
        for ax in [self.ax1_prior, self.ax2_current, self.ax3_spiral]:
            ax.set_xlim([-max_r*1.2, max_r*1.2]); ax.set_ylim([-max_r*1.2, max_r*1.2]); ax.set_zlim([0, max_z+2])
            ax.set_xlabel("X",fontsize=7); ax.set_ylabel("Y",fontsize=7); ax.set_zlabel("Z",fontsize=7)
            ax.grid(False); ax.xaxis.set_pane_color((0.05,0.05,0.05,1)); ax.yaxis.set_pane_color((0.05,0.05,0.05,1)); ax.zaxis.set_pane_color((0.05,0.05,0.05,1))
        self.canvas.draw()


    def _update_plot_iterative(self):
        self._update_plot() 

    def _update_plot(self):
        # ... (update_plot remains mostly the same, ensure it uses self.visualization_frame_counter)
        prior_entry, current_entry, full_spiral_coords = get_spiral_plot_data(self.visualization_frame_counter)
        self.ax1_prior.clear(); self.ax2_current.clear(); self.ax3_spiral.clear()
        self.ax1_prior.set_title("Prior (P)", fontsize=9); self.ax2_current.set_title("Current (C)", fontsize=9)
        self.ax3_spiral.set_title(f"Sigil Spiral ({len(spiral_cache)}/{SPIRAL_CACHE_MAXLEN})", fontsize=9)

        if prior_entry:
            px,py,pz = prior_entry["coords"]
            self.ax1_prior.scatter(px,py,pz, color='#00FFFF', s=80, marker='o', edgecolors='white', linewidth=0.5)
            self.ax1_prior.text(px,py,pz, f" {prior_entry['index']}", color='cyan', fontsize=7)
        if current_entry:
            cx,cy,cz = current_entry["coords"]
            self.ax2_current.scatter(cx,cy,cz, color='#FF00FF', s=100, marker='*', edgecolors='white', linewidth=0.5)
            self.ax2_current.text(cx,cy,cz, f" {current_entry['index']}", color='magenta', fontsize=7)

        all_x = [c[0] for c in full_spiral_coords] if full_spiral_coords else [0]
        all_y = [c[1] for c in full_spiral_coords] if full_spiral_coords else [0]
        all_z = [c[2] for c in full_spiral_coords] if full_spiral_coords else [0]
        min_x, max_x = (min(all_x)-1, max(all_x)+1) if all_x else (-1,1)
        min_y, max_y = (min(all_y)-1, max(all_y)+1) if all_y else (-1,1)
        min_z, max_z = (min(all_z), max(all_z)+1) if all_z else (0,1)
        if min_z < 0 : min_z = 0 
        
        max_dim = max(max_x-min_x, max_y-min_y, max_z-min_z, 2.0)/2.0
        mid_x, mid_y, mid_z = (min_x+max_x)/2.0, (min_y+max_y)/2.0, (min_z+max_z)/2.0

        for i, entry in enumerate(spiral_cache):
            x,y,z = entry["coords"]
            color = "yellow" if entry["end_bool"] else "#FF5733"
            # Index for size/alpha based on its position in the current cache, not absolute index
            cache_pos_idx = spiral_cache.index(entry) # More robust way to get current position in deque
            marker_size = 20 + cache_pos_idx * 2 
            alpha_val = 0.5 + (cache_pos_idx / len(spiral_cache)) * 0.5 if spiral_cache else 0.5
            
            self.ax3_spiral.scatter(x,y,z, color=color, s=marker_size, alpha=alpha_val, marker='o', edgecolors='grey', linewidth=0.3)
            self.ax3_spiral.text(x,y,z, f" {entry['index']}", color='lightgrey', fontsize=6)
            if i > 0: # Check if not the first element in the current cache for line drawing
                 # Find previous element *in the current cache view*
                if entry != spiral_cache[0]: # Ensure there's a previous element in the current deque
                    prev_entry_in_cache = spiral_cache[spiral_cache.index(entry) -1]
                    prev_x, prev_y, prev_z = prev_entry_in_cache["coords"]
                    self.ax3_spiral.plot([prev_x, x], [prev_y, y], [prev_z, z], color='grey', linestyle='-', linewidth=0.5, alpha=0.4)

        for ax in [self.ax1_prior, self.ax2_current, self.ax3_spiral]:
            ax.set_xlabel("X",fontsize=7); ax.set_ylabel("Y",fontsize=7); ax.set_zlabel("Z",fontsize=7)
            ax.set_facecolor('black'); ax.tick_params(colors='grey', labelsize=6); ax.grid(False)
            ax.xaxis.set_pane_color((0.05,0.05,0.05,1)); ax.yaxis.set_pane_color((0.05,0.05,0.05,1)); ax.zaxis.set_pane_color((0.05,0.05,0.05,1))
            ax.set_xlim([mid_x-max_dim, mid_x+max_dim]); ax.set_ylim([mid_y-max_dim, mid_y+max_dim])
            ax.set_zlim([min_z if min_z < mid_z-max_dim else mid_z-max_dim, mid_z+max_dim])
        self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    app = Octa13EncoderDecoderApp(root)
    root.mainloop()
