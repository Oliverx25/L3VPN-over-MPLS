#!/usr/bin/env python3
"""Cliente HTTP que sale por la IP de la sucursal.

ORIGEN y DESTINO se leen del entorno para poder apuntar la misma
imagen a la LAN de A, a la de B o al prefijo exclusivo 10.202.20.10.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import urllib.error
import urllib.request

ORIGEN = os.environ.get("ORIGEN", "10.10.10.10")
DESTINO = os.environ.get("DESTINO", "10.20.20.10")
PUERTO = int(os.environ.get("PUERTO", "8080"))


class ConexionOrigen(http.client.HTTPConnection):
    """Fija la dirección de origen para no salir por la gestión."""

    def connect(self) -> None:
        self.sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
            source_address=(ORIGEN, 0),
        )


class ManejadorOrigen(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request):
        return self.do_open(ConexionOrigen, req)


def llamar(ruta: str, datos: dict | None = None, clave: str | None = None, timeout: float = 4) -> int:
    url = f"http://{DESTINO}:{PUERTO}{ruta}"
    cuerpo = None if datos is None else json.dumps(datos).encode()
    metodo = "GET" if datos is None else "POST"
    solicitud = urllib.request.Request(url, data=cuerpo, method=metodo)
    if datos is not None:
        solicitud.add_header("Content-Type", "application/json")
    if clave:
        solicitud.add_header("Idempotency-Key", clave)
    abridor = urllib.request.build_opener(ManejadorOrigen)
    try:
        with abridor.open(solicitud, timeout=timeout) as respuesta:
            print(respuesta.status)
            print(respuesta.read().decode())
            return respuesta.status
    except urllib.error.HTTPError as error:
        print(error.code)
        print(error.read().decode())
        return error.code
    except urllib.error.URLError as error:
        print(f"sin respuesta: {error.reason}")
        return 0


def main() -> None:
    analizador = argparse.ArgumentParser(description="Cliente de pedidos de la sucursal")
    subcomandos = analizador.add_subparsers(dest="accion", required=True)
    subcomandos.add_parser("salud")
    subcomandos.add_parser("sonda")
    alta = subcomandos.add_parser("alta")
    alta.add_argument("--clave", required=True)
    alta.add_argument("--articulo", required=True)
    alta.add_argument("--cantidad", type=int, required=True)
    consulta = subcomandos.add_parser("consultar")
    consulta.add_argument("folio")
    args = analizador.parse_args()

    if args.accion in ("salud", "sonda"):
        llamar("/salud")
    elif args.accion == "alta":
        llamar(
            "/pedidos",
            {"articulo": args.articulo, "cantidad": args.cantidad},
            args.clave,
        )
    else:
        llamar(f"/pedidos/{args.folio}")


if __name__ == "__main__":
    main()
