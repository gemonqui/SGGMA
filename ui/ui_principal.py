"""
ui/ui_principal.py
Ventana principal del SGGMA: menú con botones grandes hacia cada módulo.

CONTRATO PARA LOS DEMÁS ARCHIVOS DE /ui
---------------------------------------
Cada módulo debe definir al nivel del archivo una función:

    def abrir_ventana(padre, conexion):
        ventana = tk.Toplevel(padre)
        ...
        return ventana      # se devuelve para evitar abrir dos ventanas iguales

Para agregar un módulo nuevo solo hay que añadir una línea a MODULOS.
Mientras un archivo no exista, el botón muestra "módulo en desarrollo"
y el resto del sistema sigue funcionando (así se puede trabajar en paralelo).
"""

import importlib
import tkinter as tk
from tkinter import ttk, messagebox

# (texto del botón, nombre del archivo en /ui)
MODULOS = [
    ("Productos",   "ui_productos"),
    ("Categorías",  "ui_categorias"),
    ("Proveedores", "ui_proveedores"),
    ("Clientes",    "ui_clientes"),
    ("Ventas",      "ui_ventas"),
    ("Compras",     "ui_compras"),
    ("Admin",       "ui_admin"),
]

COLUMNAS = 3


class VentanaPrincipal:
    def __init__(self, raiz, conexion):
        self.raiz = raiz
        self.conexion = conexion
        self.ventanas_abiertas = {}   # nombre_modulo -> Toplevel

        self._configurar_ventana()
        self._configurar_estilos()
        self._crear_widgets()

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------
    def _configurar_ventana(self):
        self.raiz.title("SGGMA - Sistema de Gestión de GeMMa Mini Abastecedor")
        ancho, alto = 760, 520
        x = (self.raiz.winfo_screenwidth() - ancho) // 2
        y = (self.raiz.winfo_screenheight() - alto) // 2
        self.raiz.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.raiz.minsize(640, 460)
        self.raiz.protocol("WM_DELETE_WINDOW", self._salir)

    def _configurar_estilos(self):
        estilo = ttk.Style(self.raiz)
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 20, "bold"))
        estilo.configure("Subtitulo.TLabel", font=("Segoe UI", 11))
        estilo.configure("Modulo.TButton", font=("Segoe UI", 13, "bold"), padding=(10, 22))

    def _crear_widgets(self):
        marco = ttk.Frame(self.raiz, padding=20)
        marco.pack(fill="both", expand=True)

        ttk.Label(marco, text="GeMMa Mini Abastecedor",
                  style="Titulo.TLabel").pack(pady=(0, 2))
        ttk.Label(marco, text="Seleccione un módulo para comenzar",
                  style="Subtitulo.TLabel").pack(pady=(0, 18))

        # Cuadrícula de botones: 3 columnas que se estiran con la ventana.
        cuadricula = ttk.Frame(marco)
        cuadricula.pack(fill="both", expand=True)
        for columna in range(COLUMNAS):
            cuadricula.columnconfigure(columna, weight=1, uniform="botones")

        total = len(MODULOS)
        for indice, (texto, modulo) in enumerate(MODULOS):
            fila, columna = divmod(indice, COLUMNAS)
            cuadricula.rowconfigure(fila, weight=1)
            boton = ttk.Button(
                cuadricula, text=texto, style="Modulo.TButton",
                command=lambda t=texto, m=modulo: self.abrir_modulo(t, m),
            )
            # El último botón (Admin) ocupa todo el ancho de su fila.
            if indice == total - 1 and columna == 0:
                boton.grid(row=fila, column=0, columnspan=COLUMNAS,
                           sticky="nsew", padx=8, pady=8)
            else:
                boton.grid(row=fila, column=columna, sticky="nsew", padx=8, pady=8)

        ttk.Button(marco, text="Salir", command=self._salir).pack(pady=(14, 0))

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def abrir_modulo(self, titulo, nombre_modulo):
        """Abre la ventana del módulo (una sola instancia por módulo)."""
        existente = self.ventanas_abiertas.get(nombre_modulo)
        if existente is not None and existente.winfo_exists():
            existente.deiconify()
            existente.lift()
            existente.focus_force()
            return

        try:
            modulo = importlib.import_module(f"ui.{nombre_modulo}")
        except ModuleNotFoundError as error:
            # Solo se trata como "en desarrollo" si falta ESTE archivo,
            # no una dependencia interna que tenga el módulo.
            if error.name == f"ui.{nombre_modulo}":
                messagebox.showinfo("Módulo en desarrollo",
                                    f"El módulo '{titulo}' todavía no está disponible.",
                                    parent=self.raiz)
                return
            raise

        if not hasattr(modulo, "abrir_ventana"):
            messagebox.showerror("Error",
                                 f"ui/{nombre_modulo}.py debe definir abrir_ventana(padre, conexion).",
                                 parent=self.raiz)
            return

        try:
            ventana = modulo.abrir_ventana(self.raiz, self.conexion)
        except Exception as error:
            messagebox.showerror("Error",
                                 f"No se pudo abrir el módulo '{titulo}':\n{error}",
                                 parent=self.raiz)
            return

        if ventana is not None:
            self.ventanas_abiertas[nombre_modulo] = ventana

    def _salir(self):
        if messagebox.askokcancel("Salir", "¿Desea cerrar el sistema?", parent=self.raiz):
            self.raiz.destroy()
