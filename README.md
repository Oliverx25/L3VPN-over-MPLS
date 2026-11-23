# L3VPN sobre MPLS

Este repositorio contiene dos laboratorios de Containerlab. Los dos arman una VPN de capa 3 sobre un backbone MPLS con FRRouting, y se despliegan por separado. El primero es la referencia corta que ya está probada. El segundo es la red empresarial que se construye a partir de esa referencia.

Los comandos se ejecutan en la VM Linux `mpls-node` de OrbStack, desde la terminal de Cursor. El kernel de macOS no reenvía MPLS.

## Los dos proyectos

| | [MPLS-CORP](MPLS-CORP/README.md) | [MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/README.md) |
| --- | --- | --- |
| Papel | Laboratorio sencillo. Enseña el mecanismo con el mínimo de nodos. | Laboratorio de exposición. Dos empresas comparten el backbone. |
| Nodos | 5: `ce1`, `pe1`, `p`, `pe2`, `ce2` | 12: las dos empresas, sus PCs y servidores, y un segundo P |
| Cliente | Un cliente, una VRF `CUST` | Empresa A en `CUST` y empresa B en `CUST_B`, con las mismas IP de LAN |
| Núcleo | Un solo P. PE1 impone dos etiquetas y P hace PHP | Dos P. Hay camino principal, respaldo y costos OSPF explícitos |
| Qué se demuestra | Ping entre las LAN simuladas en la loopback de cada CE, y la pila MPLS a ambos lados de P | Un pedido HTTP de la sucursal al centro de datos, el aislamiento entre empresas y la salida alternativa si cae un enlace |
| Gestión | `172.20.20.0/24` | `172.20.21.0/24` |
| Topología | [`mpls-corp.clab.yml`](MPLS-CORP/mpls-corp.clab.yml) | [`mpls-empresa.clab.yml`](MPLS-EMPRESARIAL/mpls-empresa.clab.yml) |
| Cómo ejecutarlo | [Guía de MPLS-CORP](MPLS-CORP/GUIA_EJECUCION_Y_PRUEBAS.md) | [Guía de MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/GUIA_EJECUCION_Y_PRUEBAS.md) |

En el MacBook Air M1 conviene tener levantado un solo laboratorio. Las redes de gestión ya están separadas por si hace falta comparar los dos en la misma VM.

## Por dónde empezar

1. Preparar la VM, Docker, Containerlab y los módulos del kernel con las secciones 1 y 2 de la [guía de MPLS-CORP](MPLS-CORP/GUIA_EJECUCION_Y_PRUEBAS.md). Esa preparación sirve para los dos proyectos.
2. Desplegar y probar [MPLS-CORP](MPLS-CORP/README.md) hasta el ping entre sucursales y la captura con dos etiquetas a la entrada de P y una a la salida.
3. Seguir con [MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/README.md). El diseño completo, incluidas las fases que todavía no están en el YAML, está en [el plan](MPLS-EMPRESARIAL/PLAN_MPLS_EMPRESARIAL.md).

## Qué hay en cada carpeta

```text
MPLS-CORP/
  README.md                      Qué es el laboratorio sencillo
  GUIA_EJECUCION_Y_PRUEBAS.md    Despliegue, pruebas y resultados esperados
  mpls-corp.clab.yml             Cinco nodos
  configs/                       FRR de pe1, p y pe2

MPLS-EMPRESARIAL/
  README.md                      Qué es la red de dos empresas
  GUIA_EJECUCION_Y_PRUEBAS.md    Despliegue, pruebas y resultados esperados
  PLAN_MPLS_EMPRESARIAL.md       Diseño por fases, defensa y trabajo siguiente
  mpls-empresa.clab.yml          Doce nodos
  configs/                       FRR de pe1, p, p2 y pe2
  apps/pedidos/                  API y cliente del pedido
```

`containerlab deploy` crea `clab-mpls-corp/` o `clab-mpls-empresa/` junto al YAML. Esa carpeta es estado del despliegue, no parte del diseño.
