"""
ui/ui_admin.py
Módulo Admin (CRUD 5): historial de ventas y compras con edición y anulación.

- Se pide la contraseña maestra; mientras no sea correcta no se muestra ningún dato.
- El acceso es temporal: se pierde al cerrar esta ventana.
- Editar / Anular ajustan el inventario automáticamente (transaccional, en servicios.py):
    * anular venta  -> devuelve el stock      * anular compra -> resta el stock
    * editar        -> ajusta el stock según la diferencia de cantidades
  Anular NO borra: el registro queda marcado como ANULADA y se conserva para auditoría.
  Una transacción anulada no se puede editar ni anular otra vez.
  Si el ajuste dejaría stock negativo, servicios.py rechaza la operación.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import servicios
from servicios import ErrorNegocio


def abrir_ventana(padre, conexion):
    """Función que llama ui_principal.py; devuelve el Toplevel creado."""
    return VentanaAdmin(padre, conexion)


def _dinero(valor):
    return f"{valor:,.2f}"


# Diferencias entre ventas y compras, para reutilizar la misma pestaña.
CONFIG = {
    "venta": {
        "titulo": "venta", "titulo_pestana": "Historial de Ventas", "columna_entidad": "Cliente",
        "campo_id": "id_venta", "campo_entidad": "cliente", "campo_id_detalle": "id_detalle_venta",
        "listar": servicios.listar_ventas, "detalle": servicios.obtener_detalle_venta,
        "eliminar": servicios.eliminar_venta, "editar": servicios.editar_venta,
        "aviso_anular": "Se DEVOLVERÁ al inventario el stock de los productos vendidos.",
    },
    "compra": {
        "titulo": "compra", "titulo_pestana": "Historial de Compras", "columna_entidad": "Proveedor",
        "campo_id": "id_compra", "campo_entidad": "proveedor", "campo_id_detalle": "id_detalle_compra",
        "listar": servicios.listar_compras, "detalle": servicios.obtener_detalle_compra,
        "eliminar": servicios.eliminar_compra, "editar": servicios.editar_compra,
        "aviso_anular": "Se RESTARÁ del inventario el stock que aportó esta compra.",
    },
}


def _solo_digitos(texto_nuevo):
    return texto_nuevo == "" or (texto_nuevo.isdigit() and len(texto_nuevo) <= 6)


def _solo_decimal(texto_nuevo):
    if texto_nuevo == "":
        return True
    if len(texto_nuevo) > 12:
        return False
    texto = texto_nuevo.replace(",", ".")
    return (texto.count(".") <= 1 and texto.replace(".", "").isdigit()) or texto == "."


# ======================================================================
# Ventana principal del módulo (contraseña + pestañas)
# ======================================================================
class VentanaAdmin(tk.Toplevel):
    def __init__(self, padre, conexion):
        super().__init__(padre)
        self.conexion = conexion
        self.title("Administración - Historial de transacciones")
        self.geometry("900x700")
        self.minsize(780, 600)

        self.var_clave = tk.StringVar()
        self._mostrar_login()

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------
    def _mostrar_login(self):
        self.marco_login = ttk.Frame(self, padding=30)
        self.marco_login.pack(expand=True)

        ttk.Label(self.marco_login, text="Acceso de administrador",
                  font=("Segoe UI", 16, "bold")).pack(pady=(0, 6))
        ttk.Label(self.marco_login,
                  text="Ingrese la contraseña maestra para ver y\ncorregir el historial de transacciones.",
                  justify="center").pack(pady=(0, 14))

        self.entrada_clave = ttk.Entry(self.marco_login, textvariable=self.var_clave,
                                       show="*", width=28)   # show="*": la clave no se ve
        self.entrada_clave.pack(pady=4)
        self.entrada_clave.bind("<Return>", lambda _e: self.validar_clave())
        self.entrada_clave.focus_set()

        botones = ttk.Frame(self.marco_login)
        botones.pack(pady=(12, 0))
        ttk.Button(botones, text="Ingresar", command=self.validar_clave).pack(side="left", padx=4)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=4)

    def validar_clave(self):
        clave = self.var_clave.get()
        if not clave:
            messagebox.showwarning("Acceso", "Ingrese la contraseña.", parent=self)
            return
        if not servicios.verificar_clave_admin(clave):
            messagebox.showerror("Acceso denegado", "Contraseña incorrecta.", parent=self)
            self.var_clave.set("")
            self.entrada_clave.focus_set()
            return
        self.var_clave.set("")
        self.marco_login.destroy()
        self._mostrar_pestanas()

    # ------------------------------------------------------------------
    # Pestañas (solo tras autenticarse)
    # ------------------------------------------------------------------
    def _mostrar_pestanas(self):
        ttk.Label(self, text="Modo administrador activo (se desactiva al cerrar esta ventana)",
                  foreground="#a05a00").pack(anchor="w", padx=12, pady=(10, 0))
        cuaderno = ttk.Notebook(self)
        cuaderno.pack(fill="both", expand=True, padx=12, pady=12)
        for tipo in ("venta", "compra"):
            pestana = PestanaHistorial(cuaderno, self.conexion, tipo)
            cuaderno.add(pestana, text=CONFIG[tipo]["titulo_pestana"])


# ======================================================================
# Pestaña genérica de historial (se usa para ventas y para compras)
# ======================================================================
class PestanaHistorial(ttk.Frame):
    def __init__(self, padre, conexion, tipo):
        super().__init__(padre, padding=8)
        self.conexion = conexion
        self.tipo = tipo
        self.cfg = CONFIG[tipo]
        self.var_busqueda = tk.StringVar()

        self._crear_tabla_principal()
        self._crear_detalle()
        self._crear_botones()
        self.var_busqueda.trace_add("write", lambda *_: self.cargar_tabla())
        self.cargar_tabla()

    # ------------------------------------------------------------------
    def _crear_tabla_principal(self):
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 6))
        ttk.Label(barra, text=f"Buscar (N.º, fecha o {self.cfg['columna_entidad'].lower()}):").pack(side="left")
        ttk.Entry(barra, textvariable=self.var_busqueda, width=26).pack(side="left", padx=6)
        ttk.Button(barra, text="Actualizar", command=self.cargar_tabla).pack(side="left", padx=6)

        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

        columnas = ("id", "fecha", "entidad", "total", "estado")
        encabezados = (("id", "N.º", 60, "center"), ("fecha", "Fecha y hora", 150, "center"),
                       ("entidad", self.cfg["columna_entidad"], 230, "w"), ("total", "Total", 110, "e"),
                       ("estado", "Estado", 90, "center"))
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse", height=8)
        for columna, titulo, ancho, alineacion in encabezados:
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, anchor=alineacion)
        # Marca visual: las transacciones anuladas se ven en gris y rojo.
        self.tabla.tag_configure("anulada", foreground="#a33", background="#eeeeee")
        self.tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_fila)

    def _crear_detalle(self):
        marco = ttk.LabelFrame(self, text="Detalle de la transacción seleccionada", padding=6)
        marco.pack(fill="both", expand=True, pady=(8, 0))
        columnas = ("producto", "cantidad", "precio", "subtotal")
        encabezados = (("producto", "Producto", 320, "w"), ("cantidad", "Cantidad", 80, "center"),
                       ("precio", "Precio unit.", 110, "e"), ("subtotal", "Subtotal", 120, "e"))
        self.tabla_detalle = ttk.Treeview(marco, columns=columnas, show="headings",
                                          selectmode="none", height=5)
        for columna, titulo, ancho, alineacion in encabezados:
            self.tabla_detalle.heading(columna, text=titulo)
            self.tabla_detalle.column(columna, width=ancho, anchor=alineacion)
        self.tabla_detalle.pack(fill="both", expand=True)

    def _crear_botones(self):
        botones = ttk.Frame(self)
        botones.pack(fill="x", pady=(10, 0))
        ttk.Button(botones, text="Anular Transacción", command=self.anular).pack(side="right", padx=4)
        ttk.Button(botones, text="Editar", command=self.editar).pack(side="right", padx=4)

    # ------------------------------------------------------------------
    def cargar_tabla(self):
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        self._limpiar_detalle()
        # El historial incluye las anuladas (auditoría); se distinguen por la columna Estado.
        for t in self.cfg["listar"](self.conexion, self.var_busqueda.get()):
            anulada = bool(t["anulada"])
            self.tabla.insert("", "end", iid=str(t[self.cfg["campo_id"]]),
                              tags=("anulada",) if anulada else (), values=(
                t[self.cfg["campo_id"]], t["fecha_hora"], t[self.cfg["campo_entidad"]],
                _dinero(t["total"]), "ANULADA" if anulada else "Vigente"))

    def _limpiar_detalle(self):
        for fila in self.tabla_detalle.get_children():
            self.tabla_detalle.delete(fila)

    def _id_seleccionado(self):
        """Devuelve el N.º de la transacción vigente seleccionada (o None con aviso)."""
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showinfo("Historial", f"Seleccione una {self.cfg['titulo']} de la tabla.",
                                parent=self)
            return None
        if self.tabla.set(seleccion[0], "estado") == "ANULADA":
            messagebox.showinfo("Historial",
                                f"La {self.cfg['titulo']} N.º {seleccion[0]} ya está anulada.\n"
                                "Se conserva solo para auditoría y no admite cambios.", parent=self)
            return None
        return int(seleccion[0])

    def al_seleccionar_fila(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        self._limpiar_detalle()
        for d in self.cfg["detalle"](self.conexion, int(seleccion[0])):
            self.tabla_detalle.insert("", "end", values=(
                d["producto"], d["cantidad"], _dinero(d["precio_unitario"]), _dinero(d["subtotal"])))

    # ------------------------------------------------------------------
    def anular(self):
        id_transaccion = self._id_seleccionado()
        if id_transaccion is None:
            return
        nombre = self.cfg["titulo"]
        # Doble confirmación explícita (acción irreversible).
        if not messagebox.askyesno(
                "Anular transacción",
                f"¿Está seguro de anular la {nombre} N.º {id_transaccion}?\n\n"
                f"{self.cfg['aviso_anular']}\n"
                "El registro se CONSERVA para auditoría (quedará marcado como ANULADA).\n"
                "La anulación no se puede deshacer.", parent=self):
            return
        if not messagebox.askyesno(
                "Confirmación final",
                f"Última confirmación: la {nombre} N.º {id_transaccion} quedará ANULADA y no podrá "
                "editarse ni reactivarse.\n¿Desea continuar?", icon="warning", parent=self):
            return
        try:
            self.cfg["eliminar"](self.conexion, id_transaccion)   # servicios: anula y ajusta stock
        except ErrorNegocio as error:
            messagebox.showerror("No se pudo anular", str(error), parent=self)
            return
        messagebox.showinfo("Anulada",
                            f"La {nombre} N.º {id_transaccion} fue anulada y el inventario se ajustó.\n"
                            "El registro se conserva para auditoría.", parent=self)
        self.cargar_tabla()

    def editar(self):
        id_transaccion = self._id_seleccionado()
        if id_transaccion is None:
            return
        DialogoEdicion(self, self.conexion, self.cfg, id_transaccion, al_guardar=self.cargar_tabla)


# ======================================================================
# Diálogo para editar cantidades y precios de una transacción
# ======================================================================
class DialogoEdicion(tk.Toplevel):
    def __init__(self, padre, conexion, cfg, id_transaccion, al_guardar):
        super().__init__(padre)
        self.conexion = conexion
        self.cfg = cfg
        self.id_transaccion = id_transaccion
        self.al_guardar = al_guardar
        # Copia editable de las líneas; no se toca la BD hasta pulsar "Guardar cambios".
        self.lineas = [
            {"id_detalle": d[cfg["campo_id_detalle"]], "producto": d["producto"],
             "cantidad": d["cantidad"], "precio": d["precio_unitario"]}
            for d in cfg["detalle"](conexion, id_transaccion)
        ]
        self.indice_seleccionado = None

        self.title(f"Editar {cfg['titulo']} N.º {id_transaccion}")
        self.geometry("640x500")
        self.minsize(560, 440)
        self.transient(padre)
        self.grab_set()   # ventana modal

        self.var_producto = tk.StringVar()
        self.var_cantidad = tk.StringVar()
        self.var_precio = tk.StringVar()
        self.var_total = tk.StringVar()

        self._crear_widgets()
        self._actualizar_tabla()

    def _crear_widgets(self):
        ttk.Label(self, text="Solo se pueden modificar cantidades y precios. "
                             "La fecha y el N.º no cambian.", foreground="gray").pack(
            anchor="w", padx=12, pady=(10, 4))

        marco = ttk.Frame(self)
        marco.pack(fill="both", expand=True, padx=12)
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        columnas = ("producto", "cantidad", "precio", "subtotal")
        encabezados = (("producto", "Producto", 250, "w"), ("cantidad", "Cantidad", 80, "center"),
                       ("precio", "Precio unit.", 100, "e"), ("subtotal", "Subtotal", 110, "e"))
        self.tabla = ttk.Treeview(marco, columns=columnas, show="headings", selectmode="browse", height=7)
        for columna, titulo, ancho, alineacion in encabezados:
            self.tabla.heading(columna, text=titulo)
            self.tabla.column(columna, width=ancho, anchor=alineacion)
        self.tabla.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(marco, orient="vertical", command=self.tabla.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tabla.configure(yscrollcommand=scroll.set)
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_linea)

        form = ttk.LabelFrame(self, text="Línea seleccionada", padding=10)
        form.pack(fill="x", padx=12, pady=8)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Producto:").grid(row=0, column=0, sticky="w")
        ttk.Label(form, textvariable=self.var_producto, font=("Segoe UI", 10, "bold")).grid(
            row=0, column=1, columnspan=4, sticky="w", padx=8)
        ttk.Label(form, text="Cantidad:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.var_cantidad, width=10, validate="key",
                  validatecommand=(self.register(_solo_digitos), "%P")).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(form, text="Precio unitario:").grid(row=1, column=2, sticky="e")
        ttk.Entry(form, textvariable=self.var_precio, width=14, validate="key",
                  validatecommand=(self.register(_solo_decimal), "%P")).grid(row=1, column=3, sticky="w", padx=8)
        ttk.Button(form, text="Aplicar a la línea", command=self.aplicar_linea).grid(row=1, column=4, padx=4)

        pie = ttk.Frame(self, padding=(12, 0, 12, 12))
        pie.pack(fill="x")
        ttk.Label(pie, text="Nuevo total:", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(pie, textvariable=self.var_total, font=("Segoe UI", 13, "bold")).pack(side="left", padx=8)
        ttk.Button(pie, text="Cancelar", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(pie, text="Guardar cambios", command=self.guardar).pack(side="right", padx=4)

    # ------------------------------------------------------------------
    def _actualizar_tabla(self):
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        total = 0.0
        for posicion, linea in enumerate(self.lineas):
            subtotal = round(linea["cantidad"] * linea["precio"], 2)
            total += subtotal
            self.tabla.insert("", "end", iid=str(posicion), values=(
                linea["producto"], linea["cantidad"], _dinero(linea["precio"]), _dinero(subtotal)))
        self.var_total.set(_dinero(round(total, 2)))
        if self.indice_seleccionado is not None:
            self.tabla.selection_set(str(self.indice_seleccionado))

    def al_seleccionar_linea(self, _evento=None):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        self.indice_seleccionado = int(seleccion[0])
        linea = self.lineas[self.indice_seleccionado]
        self.var_producto.set(linea["producto"])
        self.var_cantidad.set(str(linea["cantidad"]))
        self.var_precio.set(f"{linea['precio']:.2f}")

    def aplicar_linea(self):
        if self.indice_seleccionado is None:
            messagebox.showinfo("Editar", "Seleccione una línea de la tabla.", parent=self)
            return
        try:
            cantidad = int(self.var_cantidad.get())
        except ValueError:
            cantidad = 0
        if cantidad < 1:
            messagebox.showwarning("Editar", "La cantidad debe ser un entero mayor que cero.", parent=self)
            return
        try:
            precio = round(float(self.var_precio.get().replace(",", ".")), 2)
        except ValueError:
            messagebox.showwarning("Editar", "Escriba un precio unitario válido.", parent=self)
            return
        if precio < 0:
            messagebox.showwarning("Editar", "El precio no puede ser negativo.", parent=self)
            return
        self.lineas[self.indice_seleccionado]["cantidad"] = cantidad
        self.lineas[self.indice_seleccionado]["precio"] = precio
        self._actualizar_tabla()

    def guardar(self):
        if not messagebox.askyesno(
                "Confirmar modificación",
                "Se guardarán los cambios y el inventario se ajustará según la diferencia "
                "de cantidades.\n¿Desea continuar?", parent=self):
            return
        lineas = [(l["id_detalle"], l["cantidad"], l["precio"]) for l in self.lineas]
        try:
            nuevo_total = self.cfg["editar"](self.conexion, self.id_transaccion, lineas)
        except ErrorNegocio as error:
            # Hubo ROLLBACK: ni la transacción ni el inventario cambiaron.
            messagebox.showerror("No se pudo modificar", str(error), parent=self)
            return
        messagebox.showinfo("Modificada",
                            f"La {self.cfg['titulo']} se actualizó. Nuevo total: {_dinero(nuevo_total)}",
                            parent=self)
        self.destroy()
        self.al_guardar()
