"""
ui/ui_compras.py
Módulo de Compras: proveedor obligatorio, carrito temporal y confirmación.

- El Precio Unitario se escribe a mano (precio REAL pagado al proveedor).
- "Nuevo Precio Venta (Opcional)": si se llena, al confirmar la compra se actualiza el
  precio de venta del producto (en la misma transacción, vía registrar_compra).
- El carrito vive en memoria; la BD y el inventario solo cambian al "Confirmar Compra",
  que llama a servicios.registrar_compra (transacción con COMMIT / ROLLBACK).
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaCompras(padre, conexion)


def _dinero(valor):
    return f"{valor:,.2f}"


class VentanaCompras(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.carrito = []               # {"id_producto", "nombre", "precio", "cantidad", "nuevo_precio_venta"}
        self.mapa_proveedores = {}      # texto visible -> id_proveedor
        self.mapa_productos = {}        # texto visible -> id_producto

        self.title("Registrar compra")
        self.geometry("880x660")
        self.minsize(780, 580)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.var_proveedor = tk.StringVar()
        self.var_producto = tk.StringVar()
        self.var_cantidad = tk.StringVar(value="1")
        self.var_precio = tk.StringVar()
        self.var_nuevo_precio_venta = tk.StringVar()
        self.var_referencia = tk.StringVar(value="")
        self.var_total = tk.StringVar(value=_dinero(0))

        self._crear_seleccion()
        self._crear_carrito()
        self._crear_pie()
        self.recargar_combos()
        self.combo_proveedor.focus_set()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------
    @staticmethod
    def _solo_digitos(texto_nuevo):
        return texto_nuevo == "" or (texto_nuevo.isdigit() and len(texto_nuevo) <= 6)

    @staticmethod
    def _solo_decimal(texto_nuevo):
        """Permite dígitos y un separador decimal (punto o coma)."""
        if texto_nuevo == "" or len(texto_nuevo) > 12:
            return texto_nuevo == ""
        texto = texto_nuevo.replace(",", ".")
        return texto.count(".") <= 1 and texto.replace(".", "").isdigit() or texto == "."

    def _crear_seleccion(self):
        marco = ttk.LabelFrame(self, text="Datos de la compra", padding=12)
        marco.pack(fill="x", padx=12, pady=(12, 6))
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Proveedor (*):").grid(row=0, column=0, sticky="w", pady=4)
        self.combo_proveedor = ttk.Combobox(marco, textvariable=self.var_proveedor, state="readonly",
                                            postcommand=self.recargar_combos)
        self.combo_proveedor.grid(row=0, column=1, columnspan=4, sticky="ew", padx=(8, 0), pady=4)

        ttk.Label(marco, text="Producto (*):").grid(row=1, column=0, sticky="w", pady=4)
        self.combo_producto = ttk.Combobox(marco, textvariable=self.var_producto, state="readonly",
                                           postcommand=self.recargar_combos)
        self.combo_producto.grid(row=1, column=1, columnspan=4, sticky="ew", padx=(8, 0), pady=4)
        self.combo_producto.bind("<<ComboboxSelected>>", lambda _e: self._mostrar_referencia())

        ttk.Label(marco, text="Cantidad (*):").grid(row=2, column=0, sticky="w", pady=4)
        validar_entero = (self.register(self._solo_digitos), "%P")
        ttk.Entry(marco, textvariable=self.var_cantidad, width=10, validate="key",
                  validatecommand=validar_entero).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=4)

        ttk.Label(marco, text="Precio unitario (*):").grid(row=2, column=2, sticky="e", padx=(16, 0), pady=4)
        validar_decimal = (self.register(self._solo_decimal), "%P")
        entrada_precio = ttk.Entry(marco, textvariable=self.var_precio, width=14, validate="key",
                                   validatecommand=validar_decimal)
        entrada_precio.grid(row=2, column=3, sticky="w", padx=(8, 0), pady=4)
        entrada_precio.bind("<Return>", lambda _e: self.agregar_al_carrito())

        ttk.Button(marco, text="Agregar a la Compra", command=self.agregar_al_carrito).grid(
            row=2, column=4, sticky="e", padx=(16, 0), pady=4)

        # Fila 3: nuevo precio de venta (opcional)
        ttk.Label(marco, text="Nuevo Precio Venta (Opcional):").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Entry(marco, textvariable=self.var_nuevo_precio_venta, width=14, validate="key",
                  validatecommand=validar_decimal).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=4)
        ttk.Label(marco, text="Déjelo vacío para mantener el precio de venta actual.",
                  foreground="gray").grid(row=3, column=2, columnspan=3, sticky="w", padx=(16, 0))

        ttk.Label(marco, textvariable=self.var_referencia, foreground="gray").grid(
            row=4, column=1, columnspan=4, sticky="w", padx=(8, 0))

    def _crear_carrito(self):
        marco = ttk.LabelFrame(self, text="Carrito de compra", padding=8)
        marco.pack(fill="both", expand=True, padx=12, pady=6)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

        columnas = ("producto", "precio", "cantidad", "subtotal", "nuevo_pv")
        encabezados = (("producto", "Producto", 270, "w"), ("precio", "Precio unit.", 100, "e"),
                       ("cantidad", "Cantidad", 80, "center"), ("subtotal", "Subtotal", 110, "e"),
                       ("nuevo_pv", "Nuevo P. Venta", 110, "e"))
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
        ttk.Label(pie, text="Total de la compra:", style="Total.TLabel").pack(side="left")
        ttk.Label(pie, textvariable=self.var_total, style="Total.TLabel").pack(side="left", padx=10)
        ttk.Button(pie, text="Confirmar Compra", command=self.confirmar_compra).pack(side="right")

    # ------------------------------------------------------------------
    # Listas desplegables
    # ------------------------------------------------------------------
    def recargar_combos(self):
        """Proveedores y productos ACTIVOS. Se refresca al desplegar cada lista."""
        seleccion = self.var_proveedor.get()
        self.mapa_proveedores = {}
        for p in servicios.listar_proveedores(self.conexion):
            texto = p["nombre"]
            if texto in self.mapa_proveedores:
                texto = f"{texto} #{p['id_proveedor']}"
            self.mapa_proveedores[texto] = p["id_proveedor"]
        self.combo_proveedor["values"] = list(self.mapa_proveedores)
        if seleccion not in self.mapa_proveedores:
            self.var_proveedor.set("")

        seleccion = self.var_producto.get()
        self.mapa_productos = {}
        for p in servicios.listar_productos(self.conexion):
            texto = f"{p['nombre']} [{p['categoria']}] - Stock: {p['existencia']}"
            self.mapa_productos[texto] = p["id_producto"]
        self.combo_producto["values"] = list(self.mapa_productos)
        if seleccion not in self.mapa_productos:
            self.var_producto.set("")
            self.var_referencia.set("")

    def _mostrar_referencia(self):
        """Solo informativo: el precio NO se rellena, el usuario debe escribirlo."""
        id_producto = self.mapa_productos.get(self.var_producto.get())
        if id_producto is None:
            self.var_referencia.set("")
            return
        producto = servicios.obtener_producto(self.conexion, id_producto)
        self.var_referencia.set(
            f"Referencia: precio de compra registrado {_dinero(producto['precio_compra'])} "
            "(escriba el precio real pagado)")

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------
    def agregar_al_carrito(self):
        id_producto = self.mapa_productos.get(self.var_producto.get())
        if id_producto is None:
            messagebox.showwarning("Compra", "Seleccione un producto.", parent=self)
            return
        try:
            cantidad = int(self.var_cantidad.get())
        except ValueError:
            cantidad = 0
        if cantidad < 1:
            messagebox.showwarning("Compra", "La cantidad debe ser un entero mayor o igual a 1.", parent=self)
            return
        try:
            precio = round(float(self.var_precio.get().replace(",", ".")), 2)
        except ValueError:
            messagebox.showwarning("Compra", "Escriba un precio unitario válido (ej. 1250.50).", parent=self)
            return
        if precio < 0:
            messagebox.showwarning("Compra", "El precio unitario no puede ser negativo.", parent=self)
            return

        # Nuevo precio de venta: opcional (vacío = no cambiar).
        nuevo_precio_venta = None
        texto_nuevo = self.var_nuevo_precio_venta.get().strip()
        if texto_nuevo:
            try:
                nuevo_precio_venta = round(float(texto_nuevo.replace(",", ".")), 2)
            except ValueError:
                messagebox.showwarning("Compra", "El nuevo precio de venta no es un número válido.", parent=self)
                return
            if nuevo_precio_venta < 0:
                messagebox.showwarning("Compra", "El nuevo precio de venta no puede ser negativo.", parent=self)
                return

        try:
            producto = servicios.obtener_producto(self.conexion, id_producto)
        except ErrorNegocio as error:
            messagebox.showwarning("Compra", str(error), parent=self)
            return
        if producto["estado"] != "activo":
            messagebox.showwarning("Compra", f"El producto '{producto['nombre']}' está inactivo.", parent=self)
            self.recargar_combos()
            return

        # Mismo producto y mismo precio: se suman cantidades. Distinto precio: línea aparte.
        for linea in self.carrito:
            if linea["id_producto"] == id_producto and linea["precio"] == precio:
                linea["cantidad"] += cantidad
                if nuevo_precio_venta is not None:
                    linea["nuevo_precio_venta"] = nuevo_precio_venta
                break
        else:
            self.carrito.append({"id_producto": id_producto, "nombre": producto["nombre"],
                                 "precio": precio, "cantidad": cantidad,
                                 "nuevo_precio_venta": nuevo_precio_venta})
        self.var_cantidad.set("1")
        self.var_precio.set("")
        self.var_nuevo_precio_venta.set("")
        self._actualizar_carrito()

    def quitar_seleccionado(self):
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Compra", "Seleccione una línea del carrito.", parent=self)
            return
        del self.carrito[int(seleccion[0])]
        self._actualizar_carrito()

    def vaciar_carrito(self):
        if self.carrito and not messagebox.askyesno("Confirmar", "¿Desea vaciar el carrito?", parent=self):
            return
        self.carrito.clear()
        self._actualizar_carrito()

    def _actualizar_carrito(self):
        """Redibuja el Treeview (iid = posición en la lista) y recalcula el total."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        total = 0.0
        for posicion, linea in enumerate(self.carrito):
            subtotal = round(linea["precio"] * linea["cantidad"], 2)
            total += subtotal
            nuevo = linea["nuevo_precio_venta"]
            self.tabla.insert("", "end", iid=str(posicion), values=(
                linea["nombre"], _dinero(linea["precio"]), linea["cantidad"], _dinero(subtotal),
                _dinero(nuevo) if nuevo is not None else "-"))
        self.var_total.set(_dinero(round(total, 2)))

    # ------------------------------------------------------------------
    # Confirmación
    # ------------------------------------------------------------------
    def confirmar_compra(self):
        id_proveedor = self.mapa_proveedores.get(self.var_proveedor.get())
        if id_proveedor is None:
            messagebox.showwarning("Compra", "Debe seleccionar un proveedor.", parent=self)
            return
        if not self.carrito:
            messagebox.showwarning("Compra", "El carrito está vacío.", parent=self)
            return
        # {id_producto: nuevo_precio}: si un producto tiene varias líneas, vale la última indicada.
        nuevos_precios = {l["id_producto"]: l["nuevo_precio_venta"]
                          for l in self.carrito if l["nuevo_precio_venta"] is not None}
        aviso_precios = ("\nSe actualizará el precio de venta de %d producto(s)." % len(nuevos_precios)
                         if nuevos_precios else "")
        if not messagebox.askyesno(
                "Confirmar compra",
                f"Proveedor: {self.var_proveedor.get()}\nTotal: {self.var_total.get()}\n\n"
                f"¿Registrar la compra? El stock de los productos aumentará.{aviso_precios}",
                parent=self):
            return

        items = [(l["id_producto"], l["cantidad"], l["precio"]) for l in self.carrito]
        try:
            id_compra = servicios.registrar_compra(self.conexion, id_proveedor, items,
                                                   nuevos_precios_venta=nuevos_precios or None)
        except ErrorNegocio as error:
            # La transacción ya hizo ROLLBACK: el inventario no cambió.
            messagebox.showerror("No se pudo registrar la compra", str(error), parent=self)
            self.recargar_combos()
            return

        messagebox.showinfo("Compra registrada",
                            f"Compra N.º {id_compra} registrada correctamente.\nTotal: {self.var_total.get()}",
                            parent=self)
        self.carrito.clear()
        self._actualizar_carrito()
        self.var_proveedor.set("")
        self.recargar_combos()   # el stock cambió (y quizá algún precio de venta)

    def cerrar(self):
        if self.carrito and not messagebox.askyesno(
                "Salir", "Hay una compra sin confirmar. ¿Desea salir y perder el carrito?", parent=self):
            return
        self.destroy()
