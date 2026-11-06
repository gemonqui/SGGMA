"""
ui/ui_categorias.py
Módulo de Categorías: formulario de registro/edición + tabla de listado.
Toda la lógica de negocio está en servicios.py; aquí solo hay interfaz.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio

FILTROS_ESTADO = {"Activas": "activo", "Inactivas": "inactivo", "Todas": None}


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaCategorias(padre, conexion)


class VentanaCategorias(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.id_seleccionado = None    # None = modo "registrar"; número = modo "editar"

        self.title("Categorías")
        self.geometry("760x560")
        self.minsize(640, 480)

        self.var_nombre = tk.StringVar()
        self.var_descripcion = tk.StringVar()
        self.var_busqueda = tk.StringVar()
        self.var_filtro = tk.StringVar(value="Activas")

        self._crear_formulario()
        self._crear_tabla()
        self.var_busqueda.trace_add("write", lambda *_: self.cargar_tabla())
        self.cargar_tabla()
        self.entrada_nombre.focus_set()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _crear_formulario(self):
        self.marco_form = ttk.LabelFrame(self, text="Registrar categoría", padding=12)
        self.marco_form.pack(fill="x", padx=12, pady=(12, 6))
        self.marco_form.columnconfigure(1, weight=1)

        ttk.Label(self.marco_form, text="Nombre (*):").grid(row=0, column=0, sticky="w", pady=4)
        self.entrada_nombre = ttk.Entry(self.marco_form, textvariable=self.var_nombre)
        self.entrada_nombre.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(self.marco_form, text="Descripción:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_descripcion).grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=4)

        botones = ttk.Frame(self.marco_form)
        botones.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        self.boton_guardar = ttk.Button(botones, text="Guardar", command=self.guardar)
        self.boton_guardar.pack(side="left", padx=4)
        ttk.Button(botones, text="Limpiar", command=self.limpiar_formulario).pack(side="left", padx=4)
        self.boton_desactivar = ttk.Button(botones, text="Desactivar", command=self.desactivar,
                                           state="disabled")
        self.boton_desactivar.pack(side="left", padx=4)
        self.boton_reactivar = ttk.Button(botones, text="Reactivar", command=self.reactivar,
                                          state="disabled")
        self.boton_reactivar.pack(side="left", padx=4)

        # Enter en el formulario = Guardar
        self.entrada_nombre.bind("<Return>", lambda _e: self.guardar())

    def _crear_tabla(self):
        marco = ttk.LabelFrame(self, text="Listado de categorías", padding=8)
        marco.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        marco.rowconfigure(1, weight=1)
        marco.columnconfigure(0, weight=1)

        # Barra de búsqueda y filtro de estado
        barra = ttk.Frame(marco)
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(barra, text="Buscar:").pack(side="left")
        ttk.Entry(barra, textvariable=self.var_busqueda, width=28).pack(side="left", padx=6)
        ttk.Label(barra, text="Mostrar:").pack(side="left", padx=(12, 0))
        combo = ttk.Combobox(barra, textvariable=self.var_filtro, values=list(FILTROS_ESTADO),
                             state="readonly", width=10)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.cargar_tabla())

        columnas = ("id", "nombre", "descripcion", "estado")
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse")
        for columna, titulo, ancho in (("id", "ID", 50), ("nombre", "Nombre", 180),
                                       ("descripcion", "Descripción", 320), ("estado", "Estado", 80)):
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, anchor="center" if columna in ("id", "estado") else "w")
        self.tabla.tag_configure("inactivo", foreground="gray")
        self.tabla.grid(row=1, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_fila)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def cargar_tabla(self):
        """Recarga el Treeview según el filtro de estado y la búsqueda."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        categorias = servicios.listar_categorias(
            self.conexion,
            estado=FILTROS_ESTADO[self.var_filtro.get()],
            busqueda=self.var_busqueda.get(),
        )
        for c in categorias:
            etiqueta = () if c["estado"] == "activo" else ("inactivo",)
            self.tabla.insert("", "end", iid=str(c["id_categoria"]), tags=etiqueta,
                              values=(c["id_categoria"], c["nombre"], c["descripcion"] or "",
                                      c["estado"].capitalize()))

    def al_seleccionar_fila(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        categoria = servicios.obtener_categoria(self.conexion, int(seleccion[0]))
        self.id_seleccionado = categoria["id_categoria"]
        self.var_nombre.set(categoria["nombre"])
        self.var_descripcion.set(categoria["descripcion"] or "")
        self.marco_form.configure(text=f"Editar categoría (ID {self.id_seleccionado})")
        activa = categoria["estado"] == "activo"
        self.boton_desactivar.configure(state="normal" if activa else "disabled")
        self.boton_reactivar.configure(state="disabled" if activa else "normal")

    def limpiar_formulario(self):
        self.id_seleccionado = None
        self.var_nombre.set("")
        self.var_descripcion.set("")
        self.marco_form.configure(text="Registrar categoría")
        self.boton_desactivar.configure(state="disabled")
        self.boton_reactivar.configure(state="disabled")
        self.tabla.selection_remove(self.tabla.selection())
        self.entrada_nombre.focus_set()

    def guardar(self):
        """Registra una categoría nueva o actualiza la seleccionada."""
        try:
            if self.id_seleccionado is None:
                servicios.crear_categoria(self.conexion, self.var_nombre.get(),
                                          self.var_descripcion.get())
                mensaje = "Categoría registrada correctamente."
            else:
                servicios.modificar_categoria(self.conexion, self.id_seleccionado,
                                              self.var_nombre.get(), self.var_descripcion.get())
                mensaje = "Categoría actualizada correctamente."
        except ErrorNegocio as error:
            messagebox.showwarning("No se pudo guardar", str(error), parent=self)
            return
        messagebox.showinfo("Éxito", mensaje, parent=self)
        self.limpiar_formulario()
        self.cargar_tabla()

    def desactivar(self):
        if self.id_seleccionado is None:
            return
        if not messagebox.askyesno(
                "Confirmar",
                "¿Desea desactivar esta categoría?\nNo se podrá asignar a nuevos productos, "
                "pero se conserva en el historial.", parent=self):
            return
        try:
            servicios.desactivar_categoria(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()

    def reactivar(self):
        if self.id_seleccionado is None:
            return
        try:
            servicios.reactivar_categoria(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()
