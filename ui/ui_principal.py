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


# Se conservan los nombres de los archivos y el contrato abrir_ventana(padre, conexion).
MODULOS = [
    ("Productos", "ui_productos"),
    ("Categorías", "ui_categorias"),
    ("Proveedores", "ui_proveedores"),
    ("Clientes", "ui_clientes"),
    ("Ventas", "ui_ventas"),
    ("Compras", "ui_compras"),
    ("Cierre de Caja", "ui_cierre_caja"),
    ("Administración", "ui_admin"),
]

DESCRIPCIONES = {
    "ui_productos": "Precios, existencias y vencimientos.",
    "ui_categorias": "Organice los productos del negocio.",
    "ui_proveedores": "Contactos y datos de proveedores.",
    "ui_clientes": "Información de sus clientes.",
    "ui_ventas": "Prepare y registre una venta.",
    "ui_compras": "Registre entradas de mercadería.",
    "ui_cierre_caja": "Consulte los totales de cada día.",
    "ui_admin": "Revise y corrija transacciones.",
}

COLUMNAS = 4
FONDO = "#F3F6F3"
SUPERFICIE = "#FFFFFF"
VERDE = "#205C49"
VERDE_OSCURO = "#164333"
TEXTO = "#243D32"
SECUNDARIO = "#58685F"
BORDE = "#D8E2DA"


class VentanaPrincipal:
    def __init__(self, raiz, conexion):
        self.raiz = raiz
        self.conexion = conexion
        self.ventanas_abiertas = {}
        self._ventana_con_foco = None
        self._refrescando = False
        self._configurar_ventana()
        self._configurar_estilos()
        self._crear_widgets()
        self.raiz.bind_all("<FocusIn>", self._al_cambiar_foco, add="+")

    def _configurar_ventana(self):
        self.raiz.title("GeMMa | Gestión del mini abastecedor")
        ancho = min(1080, self.raiz.winfo_screenwidth() - 60)
        alto = min(650, self.raiz.winfo_screenheight() - 100)
        x = max(0, (self.raiz.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.raiz.winfo_screenheight() - alto) // 2)
        self.raiz.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.raiz.minsize(min(840, ancho), min(560, alto))
        self.raiz.configure(background=FONDO)
        self.raiz.protocol("WM_DELETE_WINDOW", self._salir)

    def _configurar_estilos(self):
        """Los módulos abiertos después heredan estos estilos de ttk."""
        estilo = ttk.Style(self.raiz)
        estilo.theme_use("clam")
        estilo.configure(".", font=("Segoe UI", 10), foreground=TEXTO)
        estilo.configure("TFrame", background=FONDO)
        estilo.configure("TLabel", background=FONDO, foreground=TEXTO)
        estilo.configure("TLabelframe", background=FONDO, bordercolor=BORDE)
        estilo.configure("TLabelframe.Label", background=FONDO,
                         foreground=VERDE, font=("Segoe UI", 10, "bold"))
        estilo.configure("TButton", background=VERDE, foreground="white",
                         font=("Segoe UI", 10, "bold"), padding=(10, 7),
                         borderwidth=0, focusthickness=2, focuscolor=VERDE_OSCURO)
        estilo.map("TButton",
                   background=[("disabled", "#E3E8E3"), ("pressed", VERDE_OSCURO),
                               ("active", "#2A725B")],
                   foreground=[("disabled", "#6D786F"), ("!disabled", "white")])
        estilo.configure("Secundario.TButton", background="#E4EDE6", foreground=VERDE)
        estilo.map("Secundario.TButton",
                   background=[("disabled", "#E3E8E3"), ("active", "#D3E3D7")],
                   foreground=[("disabled", "#6D786F"), ("!disabled", VERDE)])
        estilo.configure("TEntry", padding=5, fieldbackground=SUPERFICIE,
                         foreground=TEXTO, bordercolor=BORDE)
        estilo.configure("TCombobox", padding=5, fieldbackground=SUPERFICIE,
                         background=SUPERFICIE, foreground=TEXTO, bordercolor=BORDE)
        estilo.map("TCombobox", fieldbackground=[("readonly", SUPERFICIE)],
                   foreground=[("readonly", TEXTO)],
                   selectbackground=[("readonly", VERDE)],
                   selectforeground=[("readonly", "white")])
        estilo.configure("Treeview", background=SUPERFICIE, fieldbackground=SUPERFICIE,
                         foreground=TEXTO, rowheight=29, bordercolor=BORDE)
        estilo.map("Treeview", background=[("selected", VERDE)],
                   foreground=[("selected", "white")])
        estilo.configure("Treeview.Heading", background="#E4EDE6", foreground=VERDE_OSCURO,
                         font=("Segoe UI", 10, "bold"), padding=(6, 8))
        estilo.map("Treeview.Heading", background=[("active", "#D3E3D7")])
        estilo.configure("TNotebook", background=FONDO, borderwidth=0)
        estilo.configure("TNotebook.Tab", padding=(14, 8), background="#E4EDE6")
        estilo.map("TNotebook.Tab", background=[("selected", VERDE)],
                   foreground=[("selected", "white")])
        estilo.configure("Cabecera.TFrame", background=VERDE_OSCURO)
        estilo.configure("Marca.TLabel", background=VERDE_OSCURO, foreground="white",
                         font=("Segoe UI", 26, "bold"))
        estilo.configure("Bajada.TLabel", background=VERDE_OSCURO, foreground="#E0EEE3",
                         font=("Segoe UI", 11))
        estilo.configure("Seccion.TLabel", font=("Segoe UI", 15, "bold"))
        estilo.configure("Ayuda.TLabel", foreground=SECUNDARIO)
        estilo.configure("Tarjeta.TFrame", background=SUPERFICIE)
        estilo.configure("TarjetaTitulo.TLabel", background=SUPERFICIE,
                         font=("Segoe UI", 13, "bold"))
        estilo.configure("TarjetaTexto.TLabel", background=SUPERFICIE,
                         foreground=SECUNDARIO, font=("Segoe UI", 10))

    def _crear_widgets(self):
        cabecera = ttk.Frame(self.raiz, style="Cabecera.TFrame", padding=(28, 18))
        cabecera.pack(fill="x")
        ttk.Label(cabecera, text="GeMMa", style="Marca.TLabel").pack(anchor="w")
        ttk.Label(cabecera, text="Mini Abastecedor · Gestión del negocio",
                  style="Bajada.TLabel").pack(anchor="w", pady=(2, 0))

        contenido = ttk.Frame(self.raiz, padding=(24, 18, 24, 8))
        contenido.pack(fill="both", expand=True)
        ttk.Label(contenido, text="¿Qué desea hacer hoy?",
                  style="Seccion.TLabel").pack(anchor="w")
        ttk.Label(contenido, text="Seleccione un módulo para comenzar.",
                  style="Ayuda.TLabel").pack(anchor="w", pady=(3, 14))

        cuadricula = ttk.Frame(contenido)
        cuadricula.pack(fill="both", expand=True)
        for columna in range(COLUMNAS):
            cuadricula.columnconfigure(columna, weight=1, uniform="modulos")
        for indice, (titulo, nombre_modulo) in enumerate(MODULOS):
            fila, columna = divmod(indice, COLUMNAS)
            cuadricula.rowconfigure(fila, weight=1, uniform="filas")
            borde = tk.Frame(cuadricula, background=SUPERFICIE,
                             highlightbackground=BORDE, highlightthickness=1, bd=0)
            borde.grid(row=fila, column=columna, sticky="nsew", padx=5, pady=5)
            tarjeta = ttk.Frame(borde, style="Tarjeta.TFrame", padding=12)
            tarjeta.pack(fill="both", expand=True)
            ttk.Label(tarjeta, text=titulo, style="TarjetaTitulo.TLabel").pack(anchor="w")
            descripcion = ttk.Label(tarjeta, text=DESCRIPCIONES[nombre_modulo],
                                    style="TarjetaTexto.TLabel", wraplength=165,
                                    justify="left")
            descripcion.pack(anchor="w", fill="x", pady=(6, 10))
            tarjeta.bind("<Configure>",
                         lambda evento, etiqueta=descripcion:
                         etiqueta.configure(wraplength=max(90, evento.width - 24)))
            ttk.Button(tarjeta, text="Abrir módulo",
                       command=lambda t=titulo, m=nombre_modulo:
                       self.abrir_modulo(t, m)).pack(side="bottom", fill="x")

        pie = ttk.Frame(self.raiz, padding=(28, 8, 28, 16))
        pie.pack(fill="x")
        ttk.Label(pie, text="GeMMa Mini Abastecedor",
                  style="Ayuda.TLabel").pack(side="left")
        ttk.Button(pie, text="Salir del sistema", style="Secundario.TButton",
                   command=self._salir).pack(side="right")

    def abrir_modulo(self, titulo, nombre_modulo):
        """Abre una sola instancia de cada módulo."""
        existente = self.ventanas_abiertas.get(nombre_modulo)
        if existente is not None and existente.winfo_exists():
            existente.deiconify()
            existente.lift()
            existente.focus_force()
            return
        try:
            modulo = importlib.import_module(f"ui.{nombre_modulo}")
            if not hasattr(modulo, "abrir_ventana"):
                messagebox.showerror("Error", f"No se puede abrir el módulo '{titulo}'.",
                                     parent=self.raiz)
                return
            ventana = modulo.abrir_ventana(self.raiz, self.conexion)
        except ModuleNotFoundError as error:
            if error.name == f"ui.{nombre_modulo}":
                messagebox.showinfo("Módulo en desarrollo",
                                    f"El módulo '{titulo}' todavía no está disponible.",
                                    parent=self.raiz)
            else:
                messagebox.showerror("Error", f"No se pudo abrir el módulo '{titulo}':\n{error}",
                                     parent=self.raiz)
            return
        except Exception as error:
            messagebox.showerror("Error", f"No se pudo abrir el módulo '{titulo}':\n{error}",
                                 parent=self.raiz)
            return
        if ventana is not None:
            self.ventanas_abiertas[nombre_modulo] = ventana

    def _al_cambiar_foco(self, evento):
        """Actualiza al entrar en otra ventana, sin consultar en cada campo."""
        try:
            ventana = evento.widget.winfo_toplevel()
        except (AttributeError, tk.TclError):
            return
        if ventana is self._ventana_con_foco:
            return
        self._ventana_con_foco = ventana
        if callable(getattr(ventana, "actualizar_al_volver", None)):
            self.raiz.after_idle(lambda: self._refrescar_ventana(ventana))

    def _refrescar_ventana(self, ventana):
        if self._refrescando or not ventana.winfo_exists():
            return
        foco = self.raiz.focus_get()
        if foco is None or foco.winfo_toplevel() is not ventana:
            return
        if self.raiz.grab_current() is not None:
            return  # primero se termina el diálogo modal que esté abierto
        self._refrescando = True
        try:
            ventana.actualizar_al_volver()
        except Exception as error:
            messagebox.showerror("Actualizar datos", f"No se pudo actualizar esta ventana:\n{error}",
                                 parent=ventana)
        finally:
            self._refrescando = False

    def _salir(self):
        modal = self.raiz.grab_current()
        if modal is not None:
            modal.lift()
            messagebox.showinfo("Salir del sistema", "Termine o cierre el cuadro de diálogo abierto antes de salir.",
                                parent=modal)
            return
        pendientes = []
        for titulo, modulo in MODULOS:
            ventana = self.ventanas_abiertas.get(modulo)
            if ventana is None or not ventana.winfo_exists():
                continue
            comprobar = getattr(ventana, "hay_cambios_sin_guardar", None)
            if callable(comprobar) and comprobar():
                pendientes.append(titulo)
        mensaje = "¿Desea cerrar el sistema?"
        if pendientes:
            mensaje = ("Hay datos sin guardar en: " + ", ".join(pendientes) + ".\n\n"
                       "Si cierra el sistema, se descartarán esos datos.\n"
                       "¿Desea salir de todos modos?")
        if messagebox.askokcancel("Salir del sistema", mensaje, parent=self.raiz):
            self.raiz.destroy()
