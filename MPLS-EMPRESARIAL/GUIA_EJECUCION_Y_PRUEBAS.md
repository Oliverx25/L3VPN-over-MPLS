# L3VPN empresarial · Guía de ejecución, pruebas y demostración

El objetivo es registrar un pedido desde la sucursal de cada empresa en su propio servidor, con las mismas direcciones IP, y poder cortar el enlace principal del núcleo sin perder la VPN. La prueba se completa cuando las dos aplicaciones responden con su identidad, el prefijo exclusivo de B no existe en la VRF de A, y PE1 cambia de camino al apagar P1–P2.

**Dónde ejecutar los comandos.** La preparación de la VM está en las secciones 1 y 2 de [la guía de MPLS-CORP](../MPLS-CORP/GUIA_EJECUCION_Y_PRUEBAS.md). Desde el paso 1 de esta guía, usa Bash en la terminal de Cursor conectada a `mpls-node`. Si MPLS-CORP sigue desplegado, apágalo antes en un M1: `sudo containerlab destroy -t ../MPLS-CORP/mpls-corp.clab.yml --cleanup`.

## 1. Qué despliega el proyecto

```bash
cd "/Users/oliverolvera/Documents/GitHub - Personal/L3VPN-over-MPLS/MPLS-EMPRESARIAL"
ls mpls-empresa.clab.yml configs/{pe1,pe2,p,p2}/{daemons,frr.conf} apps/pedidos/{server.py,cliente.py}
```

Doce contenedores. Cuatro routers FRR, cuatro CE Alpine y cuatro terminales Python. La gestión es `172.20.21.0/24`. El nombre de cada contenedor es `clab-mpls-empresa-<nodo>`.

| Enlace | Direcciones | Función |
| --- | --- | --- |
| `pc-a eth1` — `ce1 eth2` | `10.10.10.10/24` — `10.10.10.1/24` | LAN de la sucursal A |
| `ce1 eth1` — `pe1 eth1` | `192.168.1.1/31` — `192.168.1.0/31` | Acceso A en `CUST` |
| `pe1 eth2` — `p eth1` | `10.0.12.0/31` — `10.0.12.1/31` | Núcleo, costo 10 |
| `p eth3` — `p2 eth1` | `10.0.24.0/31` — `10.0.24.1/31` | Núcleo, costo 10 |
| `p2 eth2` — `pe2 eth3` | `10.0.43.0/31` — `10.0.43.1/31` | Núcleo, costo 10 |
| `pe1 eth3` — `p2 eth3` | `10.0.14.0/31` — `10.0.14.1/31` | Atajo, costo 60 |
| `p eth2` — `pe2 eth1` | `10.0.23.0/31` — `10.0.23.1/31` | Respaldo lejano, costo 90 |
| `pe2 eth2` — `ce2 eth1` | `192.168.2.0/31` — `192.168.2.1/31` | Acceso A en `CUST` |
| `ce2 eth2` — `srv-a eth1` | `10.20.20.1/24` — `10.20.20.10/24` | LAN del centro de datos A |
| `pc-b eth1` — `ce-b1 eth2` | `10.10.10.10/24` — `10.10.10.1/24` | LAN de la sucursal B |
| `ce-b1 eth1` — `pe1 eth4` | `192.168.11.1/31` — `192.168.11.0/31` | Acceso B en `CUST_B` |
| `pe2 eth4` — `ce-b2 eth1` | `192.168.12.0/31` — `192.168.12.1/31` | Acceso B en `CUST_B` |
| `ce-b2 eth2` — `srv-b eth1` | `10.20.20.1/24` — `10.20.20.10/24` | LAN del centro de datos B |

`srv-b` suma `10.202.20.10/32` en `lo`. Ese prefijo solo se anuncia dentro de `CUST_B`.

- **OSPF y LDP.** Los cuatro routers publican su loopback en el área 0. El costo de cada enlace está en los dos extremos. LDP usa la loopback como dirección de transporte y solo habla por interfaces de núcleo.
- **VRF.** PE1 y PE2 crean `CUST` (tabla 100) y `CUST_B` (tabla 200). La estática de cada LAN vive en la VRF del cliente. RT `65000:100` para A y `65000:200` para B. El RD de A es `65000:1` en los dos PE. El de B es `65000:201` en PE1 y `65000:202` en PE2.
- **Aplicación.** `srv-a` y `srv-b` ejecutan [server.py](apps/pedidos/server.py) en el puerto 8080. La variable `EMPRESA` vale `A` o `B`. Cada uno tiene su SQLite en `/tmp`. [cliente.py](apps/pedidos/cliente.py) abre el socket desde `10.10.10.10`.

Las imágenes usan el tag `latest` en FRR y `3.12-alpine` en las terminales. Anota la versión efectiva con `sudo docker exec clab-mpls-empresa-p vtysh -c 'show version'`.

## 2. Desplegar

La primera vez, Docker descarga `python:3.12-alpine` además de las imágenes que ya usa MPLS-CORP.

```bash
sudo containerlab deploy -t mpls-empresa.clab.yml
sudo containerlab inspect -t mpls-empresa.clab.yml
```

**Verificación.** Doce nodos en `running`. En los routers el proceso principal es `sleep`: FRR arranca al final de la preparación, cuando las VRF y los sysctl MPLS ya existen. OSPF, LDP y BGP necesitan unos segundos más para llegar a `Full` y `Established`.

Para ver el dibujo dentro de la VM:

```bash
sudo containerlab graph -t mpls-empresa.clab.yml
```

Abre [el visor en el Mac](http://localhost:50080) o [el dominio de la VM](http://mpls-node.orb.local:50080). Deja esa terminal abierta. Ctrl+C cierra el visor.

## 3. Pruebas por capa

Ejecuta las pruebas en orden. Un pedido fallido con la VRF todavía vacía no dice nada de la aplicación.

### A. OSPF elige el camino de costo 30

```bash
sudo docker exec clab-mpls-empresa-p vtysh -c 'show daemons' -c 'show ip ospf neighbor'
sudo docker exec clab-mpls-empresa-p2 vtysh -c 'show ip ospf neighbor'
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route 10.255.255.3/32'
sudo docker exec clab-mpls-empresa-pe1 ping -c 4 -I 10.255.255.1 10.255.255.3
```

**Verificación.** `ospfd` aparece entre los demonios de P1. P1 ve tres vecinos `Full`: `10.255.255.1`, `10.255.255.3` y `10.255.255.4`. P2 ve a `.1`, `.2` y `.3`. PE1 instala `10.255.255.3/32` por OSPF, métrica 30, siguiente salto `10.0.12.1`, interfaz `eth2`. Las cuatro respuestas ICMP confirman el regreso. El TTL 62 de esas respuestas corresponde a los dos P del camino. El aviso de `/etc/frr/vtysh.conf` puede aparecer con las sesiones ya operativas.

En P1, la salida hacia PE2 tiene que ser P2 y no el enlace directo de costo 90:

```bash
sudo docker exec clab-mpls-empresa-p vtysh -c 'show ip route 10.255.255.3/32'
```

**Verificación.** Siguiente salto `10.0.24.1` por `eth3`.

### B. LDP en los cinco enlaces de núcleo

```bash
sudo docker exec clab-mpls-empresa-p vtysh -c 'show mpls ldp neighbor'
sudo docker exec clab-mpls-empresa-p2 vtysh -c 'show mpls ldp neighbor'
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show mpls ldp ipv4 binding' -c 'show mpls ldp neighbor'
sudo docker exec clab-mpls-empresa-pe1 ip route get 10.255.255.3 from 10.255.255.1
```

**Verificación.** P1 y P2 tienen tres vecinos `OPERATIONAL`. PE1 tiene dos, con identificadores `10.255.255.2` y `10.255.255.4`. La dirección de transporte es la loopback, no la del `/31`. La ruta del kernel hacia `10.255.255.3` muestra `encap mpls`.

`ttl-security disable` está en los cuatro `frr.conf`. Sin eso, FRR exige que la sesión TCP llegue en un solo salto. El mejor camino entre las loopbacks de PE1 y P2 pasa por P1, así que la sesión de ese par no llegaría a `OPERATIONAL` y el respaldo se quedaría sin etiqueta.

### C. Cada VRF solo ve a su empresa

```bash
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route vrf CUST'
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route vrf CUST_B'
sudo docker exec clab-mpls-empresa-pe2 vtysh -c 'show ip route vrf CUST'
sudo docker exec clab-mpls-empresa-pe2 vtysh -c 'show ip route vrf CUST_B'
```

**Verificación.**

| Router y VRF | Tiene que aparecer | No tiene que aparecer |
| --- | --- | --- |
| PE1 `CUST` | `10.10.10.0/24` estática por `192.168.1.1`; `10.20.20.0/24` BGP | `10.202.20.10/32` y `192.168.11.0/31` |
| PE1 `CUST_B` | `10.10.10.0/24` estática por `192.168.11.1`; `10.20.20.0/24` y `10.202.20.10/32` BGP | `192.168.1.0/31` |
| PE2 `CUST` | `10.20.20.0/24` estática por `192.168.2.1`; `10.10.10.0/24` BGP | `10.202.20.10/32` |
| PE2 `CUST_B` | `10.20.20.0/24` y `10.202.20.10/32` estáticas; `10.10.10.0/24` BGP | la estática de A |

La sesión que transporta esas rutas:

```bash
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show bgp ipv4 vpn summary'
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show bgp ipv4 vpn'
```

**Verificación.** Vecino `10.255.255.3` en `Established` y prefijos recibidos. En el detalle VPNv4, `10.20.20.0/24` de A lleva RD `65000:1` y el mismo prefijo de B lleva RD `65000:202`. `10.202.20.10/32` solo aparece con el RD de B.

P1 no conoce las LAN:

```bash
sudo docker exec clab-mpls-empresa-p vtysh -c 'show ip route 10.10.10.0/24' -c 'show ip route 10.20.20.0/24'
```

**Verificación.** Las dos consultas responden que la red no está en la tabla.

### D. La PC de A llega a su servidor

```bash
sudo docker exec clab-mpls-empresa-pc-a ip route get 10.20.20.10
sudo docker exec clab-mpls-empresa-srv-a tail -n 5 /tmp/pedidos.log
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py salud
```

**Verificación.** `ip route get` muestra `via 10.10.10.1 dev eth1`. El log del servidor contiene `escuchando 0.0.0.0:8080 empresa=A`. El cliente imprime `200` y un JSON con `"empresa": "A"`.

Si el cliente dice que no puede conectar, espera un segundo y revisa el log. El proceso se arranca al final del `deploy`.

### E. Dos empresas, la misma URL

Usa una clave distinta en cada empresa. Repite la de A para comprobar la idempotencia.

```bash
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py alta \
  --clave demo-A-001 --articulo "cable de red" --cantidad 2
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py alta \
  --clave demo-A-001 --articulo "cable de red" --cantidad 2
sudo docker exec clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py alta \
  --clave demo-B-001 --articulo "cable de red" --cantidad 2
sudo docker exec clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py consultar A-0001
sudo docker exec clab-mpls-empresa-srv-a tail -n 20 /tmp/pedidos.log
sudo docker exec clab-mpls-empresa-srv-b tail -n 20 /tmp/pedidos.log
```

**Verificación.**

| Llamada | Resultado esperado |
| --- | --- |
| Primera alta de A | HTTP `201`, `"empresa": "A"`, `"folio": "A-0001"`, `"solicitud": "demo-A-001"` |
| Repetición con la misma clave | HTTP `200` y el mismo folio `A-0001` |
| Alta de B a la misma URL | HTTP `201`, `"empresa": "B"`, `"folio": "B-0001"` |
| B consulta el folio de A | HTTP `404` y `"empresa": "B"` |

Los dos logs muestran origen `10.10.10.10`. Son dos servidores distintos: el de A no ve el POST de B.

### F. El prefijo exclusivo de B no entra en A

```bash
sudo docker exec clab-mpls-empresa-pc-a ip route get 10.202.20.10
sudo docker exec -e DESTINO=10.202.20.10 clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py sonda
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route vrf CUST 10.202.20.10/32'
sudo docker exec -e DESTINO=10.202.20.10 clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py sonda
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route vrf CUST_B 10.202.20.10/32'
```

**Verificación.** En `pc-a` la ruta local existe, por `10.10.10.1`, porque el CE de A también apunta ese destino hacia PE1. La sonda de A termina en `sin respuesta`. PE1 no tiene `10.202.20.10/32` en `CUST`. La sonda de B imprime `200` y `"empresa": "B"`. En `CUST_B` de PE1 el prefijo es BGP, con siguiente salto recursivo hacia `10.255.255.3`.

## 4. Lectura del paquete en el núcleo

El procedimiento de Wireshark VNC es el de la sección 6 de la [guía de MPLS-CORP](../MPLS-CORP/GUIA_EJECUCION_Y_PRUEBAS.md). Aquí cambian los puntos de captura y el filtro.

1. En el laboratorio activo, captura a la vez `pe1 eth2`, `p eth3` y `p2 eth2`.
2. Desde `pc-a`, repite una consulta de un folio que ya exista:

   ```bash
   sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py consultar A-0001
   ```

3. Filtro de visualización:

   ```text
   ip.src == 10.10.10.10 && ip.dst == 10.20.20.10 && tcp.port == 8080
   ```

| Punto, de la sucursal hacia el servidor | Cabeceras que se esperan |
| --- | --- |
| `pe1 eth1`, enlace con CE1 | Ethernet → IPv4 → TCP. Sin MPLS |
| `pe1 eth2`, salida hacia P1 | Transporte con S=0 y VPN con S=1, delante del mismo TCP |
| `p eth3`, salida hacia P2 | Dos etiquetas. La externa puede ser distinta de la que impuso PE1: P1 hizo swap. La interna se conserva |
| `p2 eth2`, salida hacia PE2 | Una etiqueta, la VPN, con S=1. P2 retiró la de transporte |
| `pe2 eth2`, enlace con CE2 | IPv4 → TCP, sin MPLS |

Los valores de etiqueta salen de este despliegue. Para argumentar el swap, compara la etiqueta externa de `pe1 eth2` con la de `p eth3` en el mismo segmento TCP (mismos puertos y número de secuencia). Para argumentar el PHP, enseña que en `p2 eth2` ya no está esa externa y la VPN sigue.

## 5. Un corte, un camino distinto

Apaga los dos extremos del enlace. OSPF retira el camino en cuanto la interfaz cae. Espera a ver la ruta nueva antes de medir la aplicación. Restaura y espera vecinos `Full` antes del siguiente evento. Un solo corte a la vez.

La métrica que muestra `show ip route` es la suma de los enlaces: 30, 70 o 100.

### Cae P1–P2

```bash
sudo docker exec clab-mpls-empresa-p ip link set eth3 down
sudo docker exec clab-mpls-empresa-p2 ip link set eth1 down
sleep 5
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route 10.255.255.3/32'
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py salud
sudo docker exec clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py salud
```

**Verificación.** Siguiente salto `10.0.14.1` por `eth3`, métrica 70. Las dos consultas de salud responden `200` con su propia empresa.

Restaura antes de seguir:

```bash
sudo docker exec clab-mpls-empresa-p ip link set eth3 up
sudo docker exec clab-mpls-empresa-p2 ip link set eth1 up
sleep 15
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip ospf neighbor' -c 'show ip route 10.255.255.3/32'
```

**Verificación.** Los dos vecinos de PE1 vuelven a `Full` y la métrica regresa a 30 por `10.0.12.1`.

### Los otros tres eventos

| Evento | Interfaces que se apagan | Siguiente salto en PE1 | Métrica |
| --- | --- | --- | --- |
| Cae PE1–P1 | `pe1 eth2` y `p eth1` | `10.0.14.1` por `eth3` | 70 |
| Cae P2–PE2 | `p2 eth2` y `pe2 eth3` | `10.0.12.1` por `eth2` | 100 |
| Cae el respaldo P1–PE2 | `p eth2` y `pe2 eth1` | `10.0.12.1` por `eth2` | 30 |

El mismo par de comandos `ip link set ... down` y, al terminar, `up`. Después de cada restauración, la ruta de PE1 tiene que volver a métrica 30 antes de apagar otro enlace. `show bgp ipv4 vpn summary` debe seguir en `Established`: el corte de un enlace de núcleo no tira la sesión si queda algún camino entre las loopbacks.

## 6. Diagnóstico y arranque limpio

| Síntoma | Primera comprobación |
| --- | --- |
| Falta un vecino OSPF | `show ip ospf neighbor` en los dos extremos de ese enlace y `ip addr show` de la interfaz. Un `ip link set down` de la sección 5 dejado activo explica el síntoma |
| `vtysh` no conecta con ningún demonio, o `show daemons` no lista `ospfd` | La VM se quedó corta de memoria y `watchfrr` abandonó el arranque. `free -h` tiene que dejar RAM disponible; con unos 2 GiB los doce nodos ya paginan. Vuelve a arrancar ese router: `sudo docker exec clab-mpls-empresa-<nodo> /usr/lib/frr/frrinit.sh start`. Los archivos `daemons` esperan 120 s antes de matar un reinicio. |
| LDP no está `OPERATIONAL` o usa la IP del `/31` | `show mpls ldp neighbor` y `show running-config`. La transporte tiene que ser `10.255.255.x` |
| La salud de A falla y la de B responde | Revisa `show ip route vrf CUST` y `show ip route vrf CUST_B` por separado. Una ruta en la VRF equivocada mezcla empresas |
| El alta de B devuelve `"empresa": "A"` | El paquete llegó al servidor de A. Revisa el RT y que `pc-b` sale por `ce-b1`, no por la LAN de A |
| `10.202.20.10` responde desde `pc-a` | PE1 tiene el prefijo en `CUST`, o `pc-a` no está usando la VPN. `ip route get` y la VRF tienen que contar la misma historia |
| El cliente imprime `sin respuesta` justo después del deploy | `tail /tmp/pedidos.log` en el servidor. Tiene que decir `escuchando` y la empresa correcta |
| Aviso de `/etc/frr/vtysh.conf` | Puede aparecer con el laboratorio sano. Contrasta con la salida del comando, no con el aviso |

Configuración que FRR está usando, frente a la del archivo montado:

```bash
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show running-config'
sudo docker logs clab-mpls-empresa-pe1 2>&1 | tail -n 80
```

Para **recrear** después de editar YAML o `configs/`:

```bash
sudo containerlab deploy -t mpls-empresa.clab.yml --reconfigure
```

Eso sustituye los contenedores. La base SQLite vive en `/tmp` y se pierde, que es lo esperable. Para **retirar** el laboratorio:

```bash
sudo containerlab destroy -t mpls-empresa.clab.yml --cleanup
```

## 7. Comandos de demostración

Con el laboratorio convergido y todos los enlaces arriba. Captura `pe1 eth2` y `p eth3` antes del último pedido si vas a mostrar el swap.

```bash
# 1. Doce nodos y la gestión 172.20.21.0/24.
sudo containerlab inspect -t mpls-empresa.clab.yml

# 2. PE1 usa el camino barato hacia el centro de datos.
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route 10.255.255.3/32'

# 3. La misma URL, dos empresas.
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py alta \
  --clave demo-A-010 --articulo "pedido en vivo" --cantidad 1
sudo docker exec clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py alta \
  --clave demo-B-010 --articulo "pedido en vivo" --cantidad 1

# 4. A no tiene ruta de VPN hacia el prefijo que solo contrató B.
sudo docker exec -e DESTINO=10.202.20.10 clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py sonda
sudo docker exec -e DESTINO=10.202.20.10 clab-mpls-empresa-pc-b python3 /opt/pedidos/cliente.py sonda

# 5. Cortar P1–P2, predecir métrica 70, y volver a consultar la salud.
sudo docker exec clab-mpls-empresa-p ip link set eth3 down
sudo docker exec clab-mpls-empresa-p2 ip link set eth1 down
sleep 5
sudo docker exec clab-mpls-empresa-pe1 vtysh -c 'show ip route 10.255.255.3/32'
sudo docker exec clab-mpls-empresa-pc-a python3 /opt/pedidos/cliente.py salud
```

**Cierre.** Muestra el `201` de cada empresa, el `sin respuesta` de A contra `10.202.20.10` junto al `200` de B, y la ruta de métrica 70. Restaura `eth3` de `p` y `eth1` de `p2` antes de terminar, y comprueba que la métrica vuelve a 30.
