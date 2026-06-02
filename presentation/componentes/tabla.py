import customtkinter as ctk
from tkinter import ttk

COLOR_BG = "#0e0e1a"
COLOR_PANEL = "#13132b"
COLOR_ACCENT = "#1a1a40"
COLOR_BORDER = "#2a2a55"
COLOR_TEXT = "#e8eaf6"
COLOR_TABLE_HEADER = "#1e1e3a"
COLOR_TABLE_ROW_EVEN = "#0c0c18"
COLOR_TABLE_ROW_ODD = "#10101f"
COLOR_GRID_LINE = "#4a4a6a"
COLOR_STATUS_OK = "#00e676"
COLOR_STATUS_RUN = "#ffd600"
COLOR_STATUS_CANCELLED = "#e74c3c"

FONT_TABLE = ("Segoe UI", 11)
FONT_TABLE_HEADER = ("Segoe UI", 11, "bold")


class ModernTable(ctk.CTkFrame):
    """Tabla con scrollbar moderna y minimalista."""

    def __init__(self, parent, headers, **kwargs):
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0,
                         border_width=0, **kwargs)

        self.headers = headers

        self.table_container = ctk.CTkFrame(self, fg_color="transparent",
                                            border_width=0)
        self.table_container.pack(fill="both", expand=True)

        # ── Scrollbar con mejor contraste ─────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Slim.Vertical.TScrollbar",
            gripcount=0,
            background="#3a3a6a",
            darkcolor="#3a3a6a",
            lightcolor="#3a3a6a",
            troughcolor="#0e0e1a",
            bordercolor="#0e0e1a",
            arrowcolor="#0e0e1a",
            arrowsize=0,
            relief="flat",
            borderwidth=0,
            width=10,
        )
        style.map(
            "Slim.Vertical.TScrollbar",
            background=[
                ("active", "#6a6aaa"),
                ("!active", "#3a3a6a"),
            ],
        )

        self.v_scrollbar = ttk.Scrollbar(
            self.table_container,
            orient="vertical",
            style="Slim.Vertical.TScrollbar",
        )
        self.v_scrollbar.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            self.table_container,
            columns=headers,
            show="headings",
            selectmode="browse",
            yscrollcommand=self.v_scrollbar.set,
        )
        self.v_scrollbar.config(command=self.tree.yview)
        self.tree.pack(side="left", fill="both", expand=True)

        for idx, header in enumerate(headers):
            self.tree.heading(header, text=header)
            if idx == 0:
                self.tree.column(header, width=210, minwidth=180, anchor="center")
            elif idx == 1:
                self.tree.column(header, width=160, minwidth=120, anchor="w")
            elif idx == 2:
                self.tree.column(header, width=250, minwidth=180, anchor="w")
            elif idx == 3:
                self.tree.column(header, width=120, minwidth=100, anchor="center")
            elif idx == 4:
                self.tree.column(header, width=120, minwidth=100, anchor="center")

        # ── Estilos de tabla — sin bordes blancos ──────────────────────
        style.configure(
            "Excel.Treeview",
            background=COLOR_TABLE_ROW_ODD,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_TABLE_ROW_ODD,
            font=FONT_TABLE,
            rowheight=32,
            borderwidth=0,
            relief="flat",
        )
        style.configure(
            "Excel.Treeview.Heading",
            background=COLOR_TABLE_HEADER,
            foreground=COLOR_TEXT,
            font=FONT_TABLE_HEADER,
            relief="flat",
            borderwidth=0,
        )
        style.map("Excel.Treeview.Heading", background=[("active", COLOR_ACCENT)])
        style.map(
            "Excel.Treeview",
            background=[("selected", COLOR_ACCENT)],
            foreground=[("selected", COLOR_TEXT)],
        )

        self.tree.configure(style="Excel.Treeview")
        self.tree.tag_configure("odd", background=COLOR_TABLE_ROW_ODD)
        self.tree.tag_configure("even", background=COLOR_TABLE_ROW_EVEN)
        self.tree.tag_configure("completed", foreground=COLOR_STATUS_OK)
        self.tree.tag_configure("pending", foreground=COLOR_STATUS_RUN)
        self.tree.tag_configure("cancelled", foreground=COLOR_STATUS_CANCELLED)

        self.row_counter = 0
        self.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    def _on_resize(self, event):
        if hasattr(self, "_resize_after") and self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(100, self._do_resize)

    def _do_resize(self):
        total_width = self.tree.winfo_width()
        if total_width <= 0:
            return
        widths = [
            int(total_width * 0.21),
            int(total_width * 0.17),
            int(total_width * 0.32),
            int(total_width * 0.15),
            int(total_width * 0.15),
        ]
        min_widths = [180, 120, 180, 100, 100]
        for i in range(len(widths)):
            if widths[i] < min_widths[i]:
                widths[i] = min_widths[i]
        for idx, header in enumerate(self.headers):
            self.tree.column(header, width=widths[idx])
        self._resize_after = None

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.row_counter = 0

    def add_row(self, row_data):
        tag = "even" if self.row_counter % 2 == 0 else "odd"
        estado = str(row_data[4]).lower() if len(row_data) > 4 else ""
        status_tag = ""
        if "completado" in estado or "finiquitado" in estado:
            status_tag = "completed"
        elif "pendiente" in estado:
            status_tag = "pending"
        elif "anulado" in estado or "cancelado" in estado:
            status_tag = "cancelled"
        final_tag = (tag, status_tag) if status_tag else (tag,)
        self.tree.insert("", "end", values=row_data, tags=final_tag)
        self.row_counter += 1

    def get_row_count(self):
        return len(self.tree.get_children())

    def scroll_to_top(self):
        self.tree.yview_moveto(0.0)

    def scroll_to_bottom(self):
        self.tree.yview_moveto(1.0)
