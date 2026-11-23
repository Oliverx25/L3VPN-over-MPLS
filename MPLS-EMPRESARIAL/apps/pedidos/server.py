#!/usr/bin/env python3
"""API de pedidos de una empresa.

La identidad sale de la variable de entorno EMPRESA. Cada contenedor
tiene su propia base SQLite, así que un folio de A no existe en B
aunque la URL y las direcciones LAN coincidan.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMPRESA = os.environ.get("EMPRESA", "A")
DB_PATH = os.environ.get("PEDIDOS_DB", "/tmp/pedidos.sqlite")
HOST = os.environ.get("PEDIDOS_HOST", "0.0.0.0")
PORT = int(os.environ.get("PEDIDOS_PORT", "8080"))

_candado = threading.Lock()


def conectar() -> sqlite3.Connection:
    conexion = sqlite3.connect(DB_PATH, check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT NOT NULL UNIQUE,
            articulo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            folio TEXT NOT NULL UNIQUE
        )
        """
    )
    conexion.commit()
    return conexion


CONN = conectar()


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato: str, *args) -> None:
        estado = args[1] if len(args) > 1 else ""
        print(
            f"origen={self.client_address[0]} {self.command} {self.path} {estado}",
            flush=True,
        )

    def _enviar(self, estado: int, carga: dict) -> None:
        cuerpo = json.dumps(carga, ensure_ascii=False).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self) -> None:  # noqa: N802
        ruta = self.path.split("?", 1)[0]
        if ruta == "/salud":
            self._enviar(200, {"empresa": EMPRESA, "estado": "ok"})
            return
        prefijo = "/pedidos/"
        if ruta.startswith(prefijo) and len(ruta) > len(prefijo):
            folio = ruta[len(prefijo) :]
            with _candado:
                fila = CONN.execute(
                    "SELECT folio, clave, articulo, cantidad FROM pedidos WHERE folio = ?",
                    (folio,),
                ).fetchone()
            if fila is None:
                self._enviar(404, {"empresa": EMPRESA, "error": "folio desconocido"})
                return
            self._enviar(
                200,
                {
                    "empresa": EMPRESA,
                    "folio": fila["folio"],
                    "solicitud": fila["clave"],
                    "articulo": fila["articulo"],
                    "cantidad": fila["cantidad"],
                },
            )
            return
        self._enviar(404, {"empresa": EMPRESA, "error": "ruta desconocida"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/pedidos":
            self._enviar(404, {"empresa": EMPRESA, "error": "ruta desconocida"})
            return
        clave = self.headers.get("Idempotency-Key", "").strip()
        if not clave:
            self._enviar(400, {"empresa": EMPRESA, "error": "falta Idempotency-Key"})
            return
        longitud = int(self.headers.get("Content-Length", "0") or "0")
        try:
            datos = json.loads(self.rfile.read(longitud) or b"{}")
            articulo = str(datos["articulo"])
            cantidad = int(datos["cantidad"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self._enviar(400, {"empresa": EMPRESA, "error": "cuerpo invalido"})
            return
        if cantidad < 1:
            self._enviar(400, {"empresa": EMPRESA, "error": "cantidad invalida"})
            return
        with _candado:
            existente = CONN.execute(
                "SELECT folio FROM pedidos WHERE clave = ?",
                (clave,),
            ).fetchone()
            if existente is not None:
                folio = existente["folio"]
                estado = 200
            else:
                cursor = CONN.execute(
                    "INSERT INTO pedidos (clave, articulo, cantidad, folio) VALUES (?, ?, ?, ?)",
                    (clave, articulo, cantidad, f"tmp-{clave}"),
                )
                folio = f"{EMPRESA}-{cursor.lastrowid:04d}"
                CONN.execute(
                    "UPDATE pedidos SET folio = ? WHERE id = ?",
                    (folio, cursor.lastrowid),
                )
                CONN.commit()
                estado = 201
        self._enviar(
            estado,
            {"empresa": EMPRESA, "folio": folio, "solicitud": clave},
        )


def main() -> None:
    servidor = ThreadingHTTPServer((HOST, PORT), Manejador)
    print(f"escuchando {HOST}:{PORT} empresa={EMPRESA}", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
