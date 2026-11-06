"""
ui/ui_ventas.py
Módulo de Ventas: selección de cliente, carrito temporal y confirmación.

- El precio de venta se toma SIEMPRE de la base de datos (no es editable).
- El carrito vive en memoria; no toca la BD ni el inventario hasta "Confirmar Venta",
  que llama a servicios.registrar_venta (transacción con COMMIT / ROLLBACK).
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio

CLIENTE_GENERAL = "Cliente General"


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaVentas(padre, conexion)


def _dinero(valor):
    return f"{valor:,.2f}"


class VentanaVentas(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.carrito = {}               # id_producto -> {"nombre", "precio", "cantidad"}
        self.mapa_clientes = {}         # texto visible -> id_cliente (None = general)
        self.mapa_productos = {}        # texto visible -> id_producto

        self.title("Registrar venta")
        self.geometry("860x640")
        self.minsize(760, 560)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.var_cliente = tk.StringVar(value=CLIENTE_GENERAL)
        self.var_producto = tk.StringVar()
        self.var_cantidad = tk.StringVar(value="1")
        self.var_precio = tk.StringVar(value="Precio unitario: -")
        self.var_total = tk.StringVar(value=_dinero(0))

        self._crear_seleccion()
        self._crear_carrito()
        self._crear_pie()
        self.recargar_combos()
        self.combo_producto.focus_set()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    @staticmethod
    def _solo_digitos(texto_nuevo):
        return texto_nuevo == "" or (texto_nuevo.isdigit() and len(texto_nuevo) <= 6)

    def _crear_seleccion(self):
        marco = ttk.LabelFrame(self, text="Datos de la venta", padding=12)
        marco.pack(fill="x", padx=12, pady=(12, 6))
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Cliente:").grid(row=0, column=0, sticky="w", pady=4)
        self.combo_cliente = ttk.Combobox(marco, textvariable=self.var_cliente, state="readonly",
                                          postcommand=self.recargar_combos)
        self.combo_cliente.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(marco, text="Producto:").grid(row=1, column=0, sticky="w", pady=4)
        self.combo_producto = ttk.Combobox(marco, textvariable=self.var_producto, state="readonly",
                                           postcommand=self.recargar_combos)
        self.combo_producto.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=4)
        self.combo_producto.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_precio())

        ttk.Label(marco, text="Cantidad:").grid(row=2, column=0, sticky="w", pady=4)
        validacion = (self.register(self._solo_digitos), "%P")
        entrada = ttk.Entry(marco, textvariable=self.var_cantidad, width=10,
                            validate="key", validatecommand=validacion)
        entrada.grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)
        entrada.bind("<Return>", lambda _e: self.agregar_al_carrito())

        ttk.Label(marco, textvariable=self.var_precio, foreground="gray").grid(
            row=2, column=2, sticky="w", padx=16)
        ttk.Button(marco, text="Agregar a la Venta", command=self.agregar_al_carrito).grid(
            row=2, column=3, sticky="e", pady=4)

    def _crear_carrito(self):
        marco = ttk.LabelFrame(self, text="Carrito", padding=8)
        marco.pack(fill="both", expand=True, padx=12, pady=6)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

        columnas = ("producto", "precio", "cantidad", "subtotal")
        encabezados = (("producto", "Producto", 320, "w"), ("precio", "Precio unit.", 110, "e"),
                       ("cantidad", "Cantidad", 90, "center"), ("subtotal", "Subtotal", 120, "e"))
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse")
        for columna, titulo, ancho, alineacion in encabezados:
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, anchor=alineacion)
        self.tabla.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)

        botones = ttk.Frame(marco)
        botones.grid(row=1, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(botones, text="Quitar seleccionado", command=self.quitar_seleccionado).pack(side="left", padx=4)
        ttk.Button(botones, text="Vaciar carrito", command=self.vaciar_carrito).pack(side="left", padx=4)

    def _crear_pie(self):
        pie = ttk.Frame(self, padding=(12, 6, 12, 12))
        pie.pack(fill="x")
        estilo = ttk.Style(self)
        estilo.configure("Total.TLabel", font=("Segoe UI", 18, "bold"))
        ttk.Label(pie, text="Total a pagar:", style="Total.TLabel").pack(side="left")
        ttk.Label(pie, textvariable=self.var_total, style="Total.TLabel").pack(side="left", padx=10)
        ttk.Button(pie, text="Confirmar Venta", command=self.confirmar_venta).pack(side="right")

    # ------------------------------------------------------------------
    # Listas desplegables
    # ------------------------------------------------------------------
    def recargar_combos(self):
        """Clientes activos y productos activos con stock. Se refresca al desplegar la lista."""
        # Clientes
        seleccion_cliente = self.var_cliente.get()
        self.mapa_clientes = {CLIENTE_GENERAL: None}
        for c in servicios.listar_clientes(self.conexion):
            texto = c["nombre"] + (f" ({c['telefono']})" if c["telefono"] else "")
            if texto in self.mapa_clientes:
                texto = f"{texto} #{c['id_cliente']}"
            self.mapa_clientes[texto] = c["id_cliente"]
        self.combo_cliente["values"] = list(self.mapa_clientes)
        if seleccion_cliente not in self.mapa_clientes:
            self.var_cliente.set(CLIENTE_GENERAL)

        # Productos (solo activos y con existencia > 0)
        seleccion_producto = self.var_producto.get()
        self.mapa_productos = {}
        for p in servicios.listar_productos(self.conexion):
            if p["existencia"] <= 0:
                continue
            texto = f"{p['nombre']} [{p['categoria']}] - Stock: {p['existencia']}"
            self.mapa_productos[texto] = p["id_producto"]
        self.combo_producto["values"] = list(self.mapa_productos)
        if seleccion_producto not in self.mapa_productos:
            self.var_producto.set("")
            self.var_precio.set("Precio unitario: -")

    def _mostrar_precio(self):
        id_producto = self.mapa_productos.get(self.var_producto.get())
        if id_producto is None:
            self.var_precio.set("Precio unitario: -")
            return
        producto = servicios.obtener_producto(self.conexion, id_producto)
        self.var_precio.set(f"Precio unitario: {_dinero(producto['precio_venta'])}")

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    def agregar_al_carrito(self):
        id_producto = self.mapa_productos.get(self.var_producto.get())
        if id_producto is None:
            messagebox.showwarning("Venta", "Seleccione un producto.", parent=self)
            return
        try:
            cantidad = int(self.var_cantidad.get())
        except ValueError:
            cantidad = 0
        if cantidad < 1:
            messagebox.showwarning("Venta", "La cantidad debe ser un entero mayor o igual a 1.", parent=self)
            return

        try:
            producto = servicios.obtener_producto(self.conexion, id_producto)
        except ErrorNegocio as error:
            messagebox.showwarning("Venta", str(error), parent=self)
            return
        if producto["estado"] != "activo":
            messagebox.showwarning("Venta", f"El producto '{producto['nombre']}' está inactivo.", parent=self)
            self.recargar_combos()
            return

        en_carrito = self.carrito.get(id_producto, {}).get("cantidad", 0)
        if en_carrito + cantidad > producto["existencia"]:
            messagebox.showwarning(
                "Stock insuficiente",
                f"Stock disponible de '{producto['nombre']}': {producto['existencia']}.\n"
                f"Ya tiene {en_carrito} en el carrito.", parent=self)
            return

        # El precio siempre viene de la BD; si el producto ya está, se suman las cantidades.
        self.carrito[id_producto] = {
            "nombre": producto["nombre"],
            "precio": producto["precio_venta"],
            "cantidad": en_carrito + cantidad,
        }
        self.var_cantidad.set("1")
        self._actualizar_carrito()

    def quitar_seleccionado(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Venta", "Seleccione una línea del carrito.", parent=self)
            return
        self.carrito.pop(int(seleccion[0]), None)
        self._actualizar_carrito()

    def vaciar_carrito(self):
        if self.carrito and not messagebox.askyesno("Confirmar", "¿Desea vaciar el carrito?", parent=self):
            return
        self.carrito.clear()
        self._actualizar_carrito()

    def _actualizar_carrito(self):
        """Redibuja el Treeview y recalcula el total."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        total = 0.0
        for id_producto, linea in self.carrito.items():
            subtotal = round(linea["precio"] * linea["cantidad"], 2)
            total += subtotal
            self.tabla.insert("", "end", iid=str(id_producto), values=(
                linea["nombre"], _dinero(linea["precio"]), linea["cantidad"], _dinero(subtotal)))
        self.var_total.set(_dinero(round(total, 2)))

    def _precios_cambiaron(self):
        """Compara los precios del carrito con la BD; si cambiaron, actualiza el carrito."""
        cambio = False
        for id_producto, linea in self.carrito.items():
            actual = servicios.obtener_producto(self.conexion, id_producto)["precio_venta"]
            if actual != linea["precio"]:
                linea["precio"] = actual
                cambio = True
        if cambio:
            self._actualizar_carrito()
        return cambio

    # ------------------------------------------------------------------
    # Confirmación
    # ------------------------------------------------------------------
    def confirmar_venta(self):
        if not self.carrito:
            messagebox.showwarning("Venta", "El carrito está vacío.", parent=self)
            return
        try:
            if self._precios_cambiaron():
                messagebox.showinfo("Precios actualizados",
                                    "Algún precio cambió desde que se agregó al carrito.\n"
                                    "Revise el nuevo total y confirme de nuevo.", parent=self)
                return
        except ErrorNegocio as error:
            messagebox.showwarning("Venta", str(error), parent=self)
            return

        if not messagebox.askyesno(
                "Confirmar venta",
                f"Cliente: {self.var_cliente.get()}\nTotal: {self.var_total.get()}\n\n¿Registrar la venta?",
                parent=self):
            return

        items = [(id_producto, linea["cantidad"]) for id_producto, linea in self.carrito.items()]
        id_cliente = self.mapa_clientes.get(self.var_cliente.get())
        try:
            id_venta = servicios.registrar_venta(self.conexion, items, id_cliente)
        except ErrorNegocio as error:
            # La transacción ya hizo ROLLBACK: el inventario no cambió.
            messagebox.showerror("No se pudo registrar la venta", str(error), parent=self)
            self.recargar_combos()
            return

        messagebox.showinfo("Venta registrada",
                            f"Venta N.º {id_venta} registrada correctamente.\nTotal: {self.var_total.get()}",
                            parent=self)
        self.carrito.clear()
        self._actualizar_carrito()
        self.var_cliente.set(CLIENTE_GENERAL)
        self.recargar_combos()   # el stock cambió

    def cerrar(self):
        if self.carrito and not messagebox.askyesno(
                "Salir", "Hay una venta sin confirmar. ¿Desea salir y perder el carrito?", parent=self):
            return
        self.destroy()
