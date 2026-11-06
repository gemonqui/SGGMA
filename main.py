"""
main.py
Punto de entrada del SGGMA. Ejecutar con:  python main.py
"""

import tkinter as tk
from tkinter import messagebox

from database import inicializar_base_datos
from ui.ui_principal import VentanaPrincipal


def main():
    # 1. Base de datos: crea el archivo y las tablas si no existen.
    try:
        conexion = inicializar_base_datos()
    except Exception as error:
        # Aún no hay ventana principal; usamos una raíz oculta solo para el mensaje.
        raiz_temporal = tk.Tk()
        raiz_temporal.withdraw()
        messagebox.showerror("Error de base de datos",
                             f"No se pudo abrir la base de datos:\n{error}")
        raiz_temporal.destroy()
        return

    # 2. Interfaz: la conexión única se comparte con todas las ventanas.
    raiz = tk.Tk()
    VentanaPrincipal(raiz, conexion)
    raiz.mainloop()

    # 3. Al cerrar la aplicación se cierra la conexión.
    conexion.close()


if __name__ == "__main__":
    main()
