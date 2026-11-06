"""
ui/ui_proveedores.py
Módulo de Proveedores: formulario de registro/edición + tabla de listado.
Toda la lógica de negocio está en servicios.py; aquí solo hay interfaz.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio

FILTROS_ESTADO = {"Activos": "activo", "Inactivos": "inactivo", "Todos": None}


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaProveedores(padre, conexion)


class VentanaProveedores(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.id_seleccionado = None    # None = modo "registrar"; número = modo "editar"

        self.title("Proveedores")
        self.geometry("900x620")
        self.minsize(780, 520)

        self.var_nombre = tk.StringVar()
        self.var_contacto = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_correo = tk.StringVar()
        self.var_direccion = tk.StringVar()
        self.var_busqueda = tk.StringVar()
        self.var_filtro = tk.StringVar(value="Activos")

        self._crear_formulario()
        self._crear_tabla()
        self.var_busqueda.trace_add("write", lambda *_: self.cargar_tabla())
        self.cargar_tabla()
        self.entrada_nombre.focus_set()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    @staticmethod
    def _solo_digitos(texto_nuevo):
        """Validación en vivo: el teléfono admite solo dígitos, máximo 12."""
        return texto_nuevo == "" or (texto_nuevo.isdigit() and len(texto_nuevo) <= 12)

    def _crear_formulario(self):
        self.marco_form = ttk.LabelFrame(self, text="Registrar proveedor", padding=12)
        self.marco_form.pack(fill="x", padx=12, pady=(12, 6))
        for columna in (1, 3):
            self.marco_form.columnconfigure(columna, weight=1, uniform="campos")

        ttk.Label(self.marco_form, text="Nombre (*):").grid(row=0, column=0, sticky="w", pady=4)
        self.entrada_nombre = ttk.Entry(self.marco_form, textvariable=self.var_nombre)
        self.entrada_nombre.grid(row=0, column=1, sticky="ew", padx=(8, 16), pady=4)

        ttk.Label(self.marco_form, text="Teléfono (*):").grid(row=0, column=2, sticky="w", pady=4)
        validacion = (self.register(self._solo_digitos), "%P")
        ttk.Entry(self.marco_form, textvariable=self.var_telefono, validate="key",
                  validatecommand=validacion).grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(self.marco_form, text="Contacto:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_contacto).grid(
            row=1, column=1, sticky="ew", padx=(8, 16), pady=4)

        ttk.Label(self.marco_form, text="Correo:").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_correo).grid(
            row=1, column=3, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(self.marco_form, text="Dirección:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_direccion).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)

        botones = ttk.Frame(self.marco_form)
        botones.grid(row=3, column=0, columnspan=4, sticky="e", pady=(8, 0))
        self.boton_guardar = ttk.Button(botones, text="Guardar", command=self.guardar)
        self.boton_guardar.pack(side="left", padx=4)
        ttk.Button(botones, text="Nuevo / Limpiar", command=self.limpiar_formulario).pack(side="left", padx=4)
        self.boton_desactivar = ttk.Button(botones, text="Desactivar", command=self.desactivar,
                                           state="disabled")
        self.boton_desactivar.pack(side="left", padx=4)
        self.boton_reactivar = ttk.Button(botones, text="Reactivar", command=self.reactivar,
                                          state="disabled")
        self.boton_reactivar.pack(side="left", padx=4)

    def _crear_tabla(self):
        marco = ttk.LabelFrame(self, text="Listado de proveedores", padding=8)
        marco.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        marco.rowconfigure(1, weight=1)
        marco.columnconfigure(0, weight=1)

        barra = ttk.Frame(marco)
        barra.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(barra, text="Buscar:").pack(side="left")
        ttk.Entry(barra, textvariable=self.var_busqueda, width=28).pack(side="left", padx=6)
        ttk.Label(barra, text="Mostrar:").pack(side="left", padx=(12, 0))
        combo = ttk.Combobox(barra, textvariable=self.var_filtro, values=list(FILTROS_ESTADO),
                             state="readonly", width=10)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.cargar_tabla())

        columnas = ("id", "nombre", "contacto", "telefono", "correo", "direccion", "estado")
        encabezados = (("id", "ID", 45, "center"), ("nombre", "Nombre", 160, "w"),
                       ("contacto", "Contacto", 120, "w"), ("telefono", "Teléfono", 85, "center"),
                       ("correo", "Correo", 160, "w"), ("direccion", "Dirección", 180, "w"),
                       ("estado", "Estado", 70, "center"))
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse")
        for columna, titulo, ancho, alineacion in encabezados:
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, anchor=alineacion)
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
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        proveedores = servicios.listar_proveedores(
            self.conexion,
            estado=FILTROS_ESTADO[self.var_filtro.get()],
            busqueda=self.var_busqueda.get(),
        )
        for p in proveedores:
            etiqueta = () if p["estado"] == "activo" else ("inactivo",)
            self.tabla.insert("", "end", iid=str(p["id_proveedor"]), tags=etiqueta, values=(
                p["id_proveedor"], p["nombre"], p["nombre_contacto"] or "", p["telefono"],
                p["correo"] or "", p["direccion"] or "", p["estado"].capitalize()))

    def al_seleccionar_fila(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        p = servicios.obtener_proveedor(self.conexion, int(seleccion[0]))
        self.id_seleccionado = p["id_proveedor"]
        self.var_nombre.set(p["nombre"])
        self.var_contacto.set(p["nombre_contacto"] or "")
        self.var_telefono.set(p["telefono"])
        self.var_correo.set(p["correo"] or "")
        self.var_direccion.set(p["direccion"] or "")
        self.marco_form.configure(text=f"Editar proveedor (ID {self.id_seleccionado})")
        activo = p["estado"] == "activo"
        self.boton_desactivar.configure(state="normal" if activo else "disabled")
        self.boton_reactivar.configure(state="disabled" if activo else "normal")

    def limpiar_formulario(self):
        self.id_seleccionado = None
        for variable in (self.var_nombre, self.var_contacto, self.var_telefono,
                         self.var_correo, self.var_direccion):
            variable.set("")
        self.marco_form.configure(text="Registrar proveedor")
        self.boton_desactivar.configure(state="disabled")
        self.boton_reactivar.configure(state="disabled")
        self.tabla.selection_remove(self.tabla.selection())
        self.entrada_nombre.focus_set()

    def guardar(self):
        """Registra un proveedor nuevo o actualiza el seleccionado."""
        datos = (self.var_nombre.get(), self.var_telefono.get(), self.var_contacto.get(),
                 self.var_correo.get(), self.var_direccion.get())
        try:
            if self.id_seleccionado is None:
                servicios.crear_proveedor(self.conexion, *datos)
                mensaje = "Proveedor registrado correctamente."
            else:
                servicios.modificar_proveedor(self.conexion, self.id_seleccionado, *datos)
                mensaje = "Proveedor actualizado correctamente."
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
                "¿Desea desactivar este proveedor?\nNo se podrá usar en nuevas compras, "
                "pero se conserva en el historial.", parent=self):
            return
        try:
            servicios.desactivar_proveedor(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()

    def reactivar(self):
        if self.id_seleccionado is None:
            return
        try:
            servicios.reactivar_proveedor(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()
