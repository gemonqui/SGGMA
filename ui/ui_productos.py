"""
ui/ui_productos.py
Módulo de Productos: formulario de registro/edición + tabla de listado.
Toda la lógica de negocio está en servicios.py; aquí solo hay interfaz.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio

FILTROS_ESTADO = {"Todos": None, "Activos": "activo", "Inactivos": "inactivo"}
SIN_PROVEEDOR = "(Sin proveedor)"


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaProductos(padre, conexion)


def _formato_dinero(valor):
    return f"{valor:,.2f}"


def _construir_mapa(filas, campo_id, campo_nombre):
    """
    Devuelve {texto_visible: id}. Si dos filas tienen el mismo nombre,
    se agrega el ID al texto para distinguirlas.
    """
    nombres = [f[campo_nombre] for f in filas]
    mapa = {}
    for fila in filas:
        texto = fila[campo_nombre]
        if nombres.count(texto) > 1:
            texto = f"{texto} (#{fila[campo_id]})"
        mapa[texto] = fila[campo_id]
    return mapa


class VentanaProductos(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.id_seleccionado = None       # None = modo "registrar"; número = modo "editar"
        self.filas_por_id = {}            # id_producto -> fila completa de listar_productos
        self.mapa_categorias = {}         # texto visible -> id_categoria
        self.mapa_proveedores = {}        # texto visible -> id_proveedor (o None)
        self._extra_categoria = None      # (id, nombre) de una categoría inactiva en edición
        self._extra_proveedor = None      # (id, nombre) de un proveedor inactivo en edición

        self.title("Productos")
        self.geometry("1000x680")
        self.minsize(860, 560)

        self.var_nombre = tk.StringVar()
        self.var_categoria = tk.StringVar()
        self.var_precio_compra = tk.StringVar()
        self.var_precio_venta = tk.StringVar()
        self.var_existencia = tk.StringVar(value="0")
        self.var_proveedor = tk.StringVar(value=SIN_PROVEEDOR)
        self.var_vencimiento = tk.StringVar()
        self.var_busqueda = tk.StringVar()
        self.var_filtro = tk.StringVar(value="Todos")

        self._crear_formulario()
        self._crear_tabla()
        self.recargar_combos()
        self.var_busqueda.trace_add("write", lambda *_: self.cargar_tabla())
        self.cargar_tabla()
        self.entrada_nombre.focus_set()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    def _crear_formulario(self):
        self.marco_form = ttk.LabelFrame(self, text="Registrar producto", padding=12)
        self.marco_form.pack(fill="x", padx=12, pady=(12, 6))
        for columna in (1, 3):
            self.marco_form.columnconfigure(columna, weight=1, uniform="campos")

        # Fila 0: nombre y categoría
        ttk.Label(self.marco_form, text="Nombre (*):").grid(row=0, column=0, sticky="w", pady=4)
        self.entrada_nombre = ttk.Entry(self.marco_form, textvariable=self.var_nombre)
        self.entrada_nombre.grid(row=0, column=1, sticky="ew", padx=(8, 16), pady=4)

        ttk.Label(self.marco_form, text="Categoría (*):").grid(row=0, column=2, sticky="w", pady=4)
        self.combo_categoria = ttk.Combobox(self.marco_form, textvariable=self.var_categoria,
                                            state="readonly", postcommand=self.recargar_combos)
        self.combo_categoria.grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)

        # Fila 1: precios
        ttk.Label(self.marco_form, text="Precio compra (*):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_precio_compra).grid(
            row=1, column=1, sticky="ew", padx=(8, 16), pady=4)

        ttk.Label(self.marco_form, text="Precio venta (*):").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_precio_venta).grid(
            row=1, column=3, sticky="ew", padx=(8, 0), pady=4)

        # Fila 2: existencia y proveedor
        self.etiqueta_existencia = ttk.Label(self.marco_form, text="Existencia inicial (*):")
        self.etiqueta_existencia.grid(row=2, column=0, sticky="w", pady=4)
        self.entrada_existencia = ttk.Entry(self.marco_form, textvariable=self.var_existencia)
        self.entrada_existencia.grid(row=2, column=1, sticky="ew", padx=(8, 16), pady=4)

        ttk.Label(self.marco_form, text="Proveedor habitual:").grid(row=2, column=2, sticky="w", pady=4)
        self.combo_proveedor = ttk.Combobox(self.marco_form, textvariable=self.var_proveedor,
                                            state="readonly", postcommand=self.recargar_combos)
        self.combo_proveedor.grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=4)

        # Fila 3: vencimiento
        ttk.Label(self.marco_form, text="Fecha vencimiento:").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(self.marco_form, textvariable=self.var_vencimiento).grid(
            row=3, column=1, sticky="ew", padx=(8, 16), pady=4)
        ttk.Label(self.marco_form, text="Formato AAAA-MM-DD (opcional)",
                  foreground="gray").grid(row=3, column=2, columnspan=2, sticky="w", pady=4)

        # Botones
        botones = ttk.Frame(self.marco_form)
        botones.grid(row=4, column=0, columnspan=4, sticky="e", pady=(8, 0))
        self.boton_guardar = ttk.Button(botones, text="Guardar", command=self.guardar)
        self.boton_guardar.pack(side="left", padx=4)
        ttk.Button(botones, text="Limpiar", command=self.limpiar_formulario).pack(side="left", padx=4)
        self.boton_desactivar = ttk.Button(botones, text="Desactivar", command=self.desactivar,
                                           state="disabled")
        self.boton_desactivar.pack(side="left", padx=4)
        self.boton_reactivar = ttk.Button(botones, text="Reactivar", command=self.reactivar,
                                          state="disabled")
        self.boton_reactivar.pack(side="left", padx=4)

    def _crear_tabla(self):
        marco = ttk.LabelFrame(self, text="Listado de productos", padding=8)
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

        columnas = ("id", "nombre", "categoria", "p_compra", "p_venta",
                    "existencia", "proveedor", "vencimiento", "estado")
        encabezados = (("id", "ID", 45, "center"), ("nombre", "Nombre", 170, "w"),
                       ("categoria", "Categoría", 110, "w"), ("p_compra", "P. Compra", 80, "e"),
                       ("p_venta", "P. Venta", 80, "e"), ("existencia", "Existencia", 75, "center"),
                       ("proveedor", "Proveedor", 120, "w"), ("vencimiento", "Vence", 90, "center"),
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
    # Listas desplegables
    # ------------------------------------------------------------------
    def recargar_combos(self):
        """
        Llena Categoría y Proveedor con registros ACTIVOS. Se ejecuta al abrir la
        ventana y cada vez que se despliega una lista, para ver cambios hechos en
        otras ventanas. Si se edita un producto con categoría/proveedor inactivo,
        ese valor se incluye para no perderlo.
        """
        categorias = [dict(c) for c in servicios.listar_categorias(self.conexion)]
        if self._extra_categoria and self._extra_categoria[0] not in [c["id_categoria"] for c in categorias]:
            categorias.append({"id_categoria": self._extra_categoria[0],
                               "nombre": self._extra_categoria[1]})
        self.mapa_categorias = _construir_mapa(categorias, "id_categoria", "nombre")
        self.combo_categoria["values"] = list(self.mapa_categorias)

        # El CRUD de proveedores se agrega en otra fase: si aún no existe, la lista queda vacía.
        funcion_proveedores = getattr(servicios, "listar_proveedores", None)
        proveedores = [dict(p) for p in funcion_proveedores(self.conexion)] if funcion_proveedores else []
        if self._extra_proveedor and self._extra_proveedor[0] not in [p["id_proveedor"] for p in proveedores]:
            proveedores.append({"id_proveedor": self._extra_proveedor[0],
                                "nombre": self._extra_proveedor[1]})
        self.mapa_proveedores = {SIN_PROVEEDOR: None}
        self.mapa_proveedores.update(_construir_mapa(proveedores, "id_proveedor", "nombre"))
        self.combo_proveedor["values"] = list(self.mapa_proveedores)

    @staticmethod
    def _texto_de_id(mapa, identificador):
        for texto, valor in mapa.items():
            if valor == identificador:
                return texto
        return ""

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def cargar_tabla(self):
        """Recarga el Treeview según el filtro de estado y la búsqueda."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self.filas_por_id = {}
        productos = servicios.listar_productos(
            self.conexion,
            estado=FILTROS_ESTADO[self.var_filtro.get()],
            busqueda=self.var_busqueda.get(),
        )
        for p in productos:
            self.filas_por_id[p["id_producto"]] = p
            etiqueta = () if p["estado"] == "activo" else ("inactivo",)
            self.tabla.insert("", "end", iid=str(p["id_producto"]), tags=etiqueta, values=(
                p["id_producto"], p["nombre"], p["categoria"],
                _formato_dinero(p["precio_compra"]), _formato_dinero(p["precio_venta"]),
                p["existencia"], p["proveedor"] or "", p["fecha_vencimiento"] or "",
                p["estado"].capitalize()))

    def al_seleccionar_fila(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        producto = self.filas_por_id[int(seleccion[0])]
        self.id_seleccionado = producto["id_producto"]

        # Si la categoría/proveedor del producto están inactivos, se incluyen en las listas.
        self._extra_categoria = (producto["id_categoria"], producto["categoria"])
        self._extra_proveedor = ((producto["id_proveedor"], producto["proveedor"])
                                 if producto["id_proveedor"] else None)
        self.recargar_combos()

        self.var_nombre.set(producto["nombre"])
        self.var_categoria.set(self._texto_de_id(self.mapa_categorias, producto["id_categoria"]))
        self.var_precio_compra.set(f"{producto['precio_compra']:.2f}")
        self.var_precio_venta.set(f"{producto['precio_venta']:.2f}")
        self.var_proveedor.set(self._texto_de_id(self.mapa_proveedores, producto["id_proveedor"]) or SIN_PROVEEDOR)
        self.var_vencimiento.set(producto["fecha_vencimiento"] or "")

        # En edición la existencia es de solo lectura: cambia únicamente con compras y ventas.
        self.var_existencia.set(str(producto["existencia"]))
        self.entrada_existencia.configure(state="disabled")
        self.etiqueta_existencia.configure(text="Existencia actual:")

        self.marco_form.configure(text=f"Editar producto (ID {self.id_seleccionado})")
        activo = producto["estado"] == "activo"
        self.boton_desactivar.configure(state="normal" if activo else "disabled")
        self.boton_reactivar.configure(state="disabled" if activo else "normal")

    def limpiar_formulario(self):
        self.id_seleccionado = None
        self._extra_categoria = None
        self._extra_proveedor = None
        self.var_nombre.set("")
        self.var_categoria.set("")
        self.var_precio_compra.set("")
        self.var_precio_venta.set("")
        self.var_existencia.set("0")
        self.var_proveedor.set(SIN_PROVEEDOR)
        self.var_vencimiento.set("")
        self.entrada_existencia.configure(state="normal")
        self.etiqueta_existencia.configure(text="Existencia inicial (*):")
        self.marco_form.configure(text="Registrar producto")
        self.boton_desactivar.configure(state="disabled")
        self.boton_reactivar.configure(state="disabled")
        self.tabla.selection_remove(self.tabla.selection())
        self.recargar_combos()
        self.entrada_nombre.focus_set()

    def guardar(self):
        """Registra un producto nuevo o actualiza el seleccionado."""
        id_categoria = self.mapa_categorias.get(self.var_categoria.get())
        if id_categoria is None:
            messagebox.showwarning("No se pudo guardar", "Debe seleccionar una categoría.", parent=self)
            return
        id_proveedor = self.mapa_proveedores.get(self.var_proveedor.get())
        # Se acepta la coma como separador decimal.
        precio_compra = self.var_precio_compra.get().replace(",", ".")
        precio_venta = self.var_precio_venta.get().replace(",", ".")

        try:
            if self.id_seleccionado is None:
                servicios.crear_producto(
                    self.conexion, self.var_nombre.get(), id_categoria, precio_compra,
                    precio_venta, self.var_existencia.get(), id_proveedor,
                    self.var_vencimiento.get())
                mensaje = "Producto registrado correctamente."
            else:
                servicios.modificar_producto(
                    self.conexion, self.id_seleccionado, self.var_nombre.get(), id_categoria,
                    precio_compra, precio_venta, id_proveedor, self.var_vencimiento.get())
                mensaje = "Producto actualizado correctamente."
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
                "¿Desea desactivar este producto?\nNo se podrá usar en compras ni ventas, "
                "pero se conserva en el historial.", parent=self):
            return
        try:
            servicios.desactivar_producto(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()

    def reactivar(self):
        if self.id_seleccionado is None:
            return
        try:
            servicios.reactivar_producto(self.conexion, self.id_seleccionado)
        except ErrorNegocio as error:
            messagebox.showwarning("Error", str(error), parent=self)
            return
        self.limpiar_formulario()
        self.cargar_tabla()
