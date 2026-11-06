"""
database.py
Sistema de Gestión de GeMMa Mini Abastecedor (SGGMA)

Responsabilidades de este módulo:
  - Abrir conexiones a SQLite con la configuración correcta.
  - Crear todas las tablas del sistema (idempotente: se puede llamar muchas veces).
  - Ofrecer un gestor de transacciones (BEGIN / COMMIT / ROLLBACK) para que
    servicios.py lo reutilice en compras, ventas y operaciones del módulo Admin.

NO contiene lógica de negocio ni consultas de los CRUD (eso va en servicios.py).
"""

import os
import re
import sqlite3
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
NOMBRE_ARCHIVO_BD = "sggma.db"
RUTA_BD = os.path.join(os.path.dirname(os.path.abspath(__file__)), NOMBRE_ARCHIVO_BD)

ESTADO_ACTIVO = "activo"
ESTADO_INACTIVO = "inactivo"


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------
def obtener_conexion(ruta_bd=None):
    """
    Devuelve una conexión nueva a la base de datos.

    - isolation_level=None  -> modo "autocommit" de Python; así controlamos las
      transacciones a mano con BEGIN / COMMIT / ROLLBACK (requisito del ERS).
    - foreign_keys=ON       -> SQLite NO activa las llaves foráneas por defecto.
    - row_factory=sqlite3.Row -> permite acceder a columnas por nombre: fila["nombre"].

    El parámetro `ruta_bd` permite usar ":memory:" o un archivo temporal en las
    pruebas unitarias sin tocar la base real.
    """
    conexion = sqlite3.connect(ruta_bd or RUTA_BD, isolation_level=None)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


@contextmanager
def transaccion(conexion):
    """
    Gestor de contexto para ejecutar un bloque como UNA sola operación atómica.

    Uso en servicios.py:
        with transaccion(conexion):
            conexion.execute("INSERT ...")
            conexion.execute("UPDATE productos SET existencia = ...")
        # Si no hubo errores -> COMMIT. Si hubo cualquier excepción -> ROLLBACK
        # y la excepción se vuelve a lanzar para que la UI muestre el mensaje.
    """
    conexion.execute("BEGIN")
    try:
        yield conexion
        conexion.execute("COMMIT")
    except Exception:
        conexion.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------
# Notas de diseño (todas salen del ERS):
#  * Borrado lógico: categorias, proveedores, productos y clientes tienen la
#    columna `estado` ('activo' / 'inactivo'). Nunca se hace DELETE sobre ellas.
#  * Compras y ventas NO se borran: el módulo Admin (CRUD 5) las ANULA
#    (anulada = 1) y revierte el inventario, conservando el registro para auditoría.
#  * Stock: CHECK (existencia >= 0) es la ÚLTIMA barrera a nivel de BD contra el
#    stock negativo; servicios.py además valida antes de escribir.
#  * Venta sin cliente = "cliente general" -> ventas.id_cliente puede ser NULL.
#  * El precio de venta unitario y el costo unitario se COPIAN al detalle de la
#    transacción (histórico), así cambiar el precio del producto después no
#    altera ventas ni compras pasadas.
ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria   INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT    NOT NULL UNIQUE
                           CHECK (length(nombre) BETWEEN 1 AND 50),
    descripcion    TEXT    CHECK (descripcion IS NULL OR length(descripcion) <= 200),
    estado         TEXT    NOT NULL DEFAULT 'activo'
                           CHECK (estado IN ('activo', 'inactivo'))
);

CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT    NOT NULL
                             CHECK (length(nombre) BETWEEN 1 AND 100),
    nombre_contacto  TEXT    CHECK (nombre_contacto IS NULL OR length(nombre_contacto) <= 100),
    telefono         TEXT    NOT NULL
                             CHECK (length(telefono) BETWEEN 8 AND 12 AND telefono NOT GLOB '*[^0-9]*'),
    correo           TEXT    CHECK (correo IS NULL OR length(correo) <= 100),
    direccion        TEXT    CHECK (direccion IS NULL OR length(direccion) <= 200),
    estado           TEXT    NOT NULL DEFAULT 'activo'
                             CHECK (estado IN ('activo', 'inactivo'))
);

CREATE TABLE IF NOT EXISTS clientes (
    id_cliente   INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT    NOT NULL
                         CHECK (length(nombre) BETWEEN 1 AND 100),
    telefono     TEXT    CHECK (telefono IS NULL
                                OR (length(telefono) BETWEEN 8 AND 12 AND telefono NOT GLOB '*[^0-9]*')),
    correo       TEXT    CHECK (correo IS NULL OR length(correo) <= 100),
    direccion    TEXT    CHECK (direccion IS NULL OR length(direccion) <= 200),
    estado       TEXT    NOT NULL DEFAULT 'activo'
                         CHECK (estado IN ('activo', 'inactivo')),
    -- No se permite duplicar nombre + teléfono (ERS: SGGMA_CLI_001 / 003)
    UNIQUE (nombre, telefono)
);

CREATE TABLE IF NOT EXISTS productos (
    id_producto        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre             TEXT    NOT NULL
                               CHECK (length(nombre) BETWEEN 1 AND 100),
    id_categoria       INTEGER NOT NULL,
    precio_compra      REAL    NOT NULL CHECK (precio_compra >= 0),
    precio_venta       REAL    NOT NULL CHECK (precio_venta  >= 0),
    existencia         INTEGER NOT NULL DEFAULT 0 CHECK (existencia >= 0),
    id_proveedor       INTEGER,                       -- proveedor habitual (opcional)
    fecha_vencimiento  TEXT,                          -- 'YYYY-MM-DD' (opcional)
    estado             TEXT    NOT NULL DEFAULT 'activo'
                               CHECK (estado IN ('activo', 'inactivo')),
    FOREIGN KEY (id_categoria) REFERENCES categorias  (id_categoria),
    FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor),
    -- No dos productos con el mismo nombre en la misma categoría
    UNIQUE (nombre, id_categoria)
);

CREATE TABLE IF NOT EXISTS compras (
    id_compra     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    id_proveedor  INTEGER NOT NULL,
    total         REAL    NOT NULL CHECK (total >= 0),
    anulada       INTEGER NOT NULL DEFAULT 0 CHECK (anulada IN (0, 1)),  -- 1 = anulada (auditoría)
    FOREIGN KEY (id_proveedor) REFERENCES proveedores (id_proveedor)
);

CREATE TABLE IF NOT EXISTS detalle_compras (
    id_detalle_compra  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_compra          INTEGER NOT NULL,
    id_producto        INTEGER NOT NULL,
    cantidad           INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario    REAL    NOT NULL CHECK (precio_unitario >= 0),  -- precio REAL pagado
    subtotal           REAL    NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (id_compra)   REFERENCES compras   (id_compra) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos (id_producto)
);

CREATE TABLE IF NOT EXISTS ventas (
    id_venta     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    id_cliente   INTEGER,                              -- NULL = cliente general
    total        REAL    NOT NULL CHECK (total >= 0),
    anulada      INTEGER NOT NULL DEFAULT 0 CHECK (anulada IN (0, 1)),  -- 1 = anulada (auditoría)
    FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente)
);

CREATE TABLE IF NOT EXISTS detalle_ventas (
    id_detalle_venta  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta          INTEGER NOT NULL,
    id_producto       INTEGER NOT NULL,
    cantidad          INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario   REAL    NOT NULL CHECK (precio_unitario >= 0),  -- copiado de productos.precio_venta
    subtotal          REAL    NOT NULL CHECK (subtotal >= 0),
    FOREIGN KEY (id_venta)    REFERENCES ventas    (id_venta) ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES productos (id_producto)
);

-- Índices para las búsquedas/filtros que pide el ERS (por proveedor, cliente, fecha, producto)
CREATE INDEX IF NOT EXISTS idx_productos_categoria   ON productos       (id_categoria);
CREATE INDEX IF NOT EXISTS idx_productos_proveedor   ON productos       (id_proveedor);
CREATE INDEX IF NOT EXISTS idx_compras_proveedor     ON compras         (id_proveedor);
CREATE INDEX IF NOT EXISTS idx_compras_fecha         ON compras         (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_detcompras_compra     ON detalle_compras (id_compra);
CREATE INDEX IF NOT EXISTS idx_detcompras_producto   ON detalle_compras (id_producto);
CREATE INDEX IF NOT EXISTS idx_ventas_cliente        ON ventas          (id_cliente);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha          ON ventas          (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_detventas_venta       ON detalle_ventas  (id_venta);
CREATE INDEX IF NOT EXISTS idx_detventas_producto    ON detalle_ventas  (id_producto);
"""


def _migrar_columna_anulada(conexion):
    """
    Bases de datos creadas ANTES de esta versión no tienen la columna `anulada`
    (CREATE TABLE IF NOT EXISTS no modifica tablas existentes). Se agrega aquí,
    conservando todos los datos; las transacciones antiguas quedan como no anuladas.
    """
    for tabla in ("ventas", "compras"):
        columnas = [fila["name"] for fila in conexion.execute(f"PRAGMA table_info({tabla})")]
        if "anulada" not in columnas:
            conexion.execute(
                f"ALTER TABLE {tabla} ADD COLUMN anulada INTEGER NOT NULL DEFAULT 0 "
                "CHECK (anulada IN (0, 1))"
            )


def _migrar_restriccion_telefono(conexion):
    """
    Bases creadas antes aceptaban teléfonos de EXACTAMENTE 8 dígitos (CHECK en la tabla).
    SQLite no permite modificar un CHECK, así que si la tabla guardada aún tiene la regla
    antigua se reconstruye con la definición actual (8 a 12 dígitos), conservando los datos.
    """
    for tabla in ("proveedores", "clientes"):
        definicion = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,)
        ).fetchone()["sql"]
        if "length(telefono) = 8" not in definicion:
            continue   # ya tiene la regla nueva
        sql_nuevo = re.search(
            rf"CREATE TABLE IF NOT EXISTS {tabla} \(.*?\n\);", ESQUEMA_SQL, re.DOTALL
        ).group(0).replace(f"IF NOT EXISTS {tabla}", f"{tabla}_nueva")
        # Con claves foráneas activas no se puede reemplazar una tabla referenciada:
        # se desactivan durante la reconstrucción y se vuelven a activar al final.
        conexion.execute("PRAGMA foreign_keys = OFF")
        try:
            conexion.execute("BEGIN")
            conexion.execute(sql_nuevo)
            conexion.execute(f"INSERT INTO {tabla}_nueva SELECT * FROM {tabla}")
            conexion.execute(f"DROP TABLE {tabla}")
            conexion.execute(f"ALTER TABLE {tabla}_nueva RENAME TO {tabla}")
            conexion.execute("COMMIT")
        except Exception:
            conexion.execute("ROLLBACK")
            raise
        finally:
            conexion.execute("PRAGMA foreign_keys = ON")


def crear_tablas(conexion):
    """Crea todas las tablas e índices si todavía no existen (y migra bases antiguas)."""
    conexion.executescript(ESQUEMA_SQL)
    _migrar_columna_anulada(conexion)
    _migrar_restriccion_telefono(conexion)


def inicializar_base_datos(ruta_bd=None):
    """
    Punto de entrada para main.py: abre la conexión, crea el esquema y
    devuelve la conexión lista para usar.
    """
    conexion = obtener_conexion(ruta_bd)
    crear_tablas(conexion)
    return conexion


if __name__ == "__main__":
    # Ejecutar `python database.py` crea el archivo sggma.db con todas las tablas.
    con = inicializar_base_datos()
    tablas = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    print("Base de datos lista en:", RUTA_BD)
    print("Tablas creadas:", ", ".join(t["name"] for t in tablas))
    con.close()
