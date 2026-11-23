# L3VPN sobre MPLS · Guía de ejecución, pruebas y demostración

El objetivo es enviar un ping de la LAN de CE1 (`10.10.10.1`) a la LAN de CE2 (`10.20.20.1`) y seguir la misma solicitud ICMP a ambos lados del router P. La prueba se completa cuando las sucursales se alcanzan en ambos sentidos y la captura muestra dónde se retira la etiqueta de transporte.

**Dónde ejecutar los comandos.** El primer paso se hace en macOS. Desde el paso 2, usa Bash en la terminal de Cursor conectada por SSH a la VM. Los comandos `docker exec` ya seleccionan el nodo correspondiente. Las secciones de instalación solo se necesitan la primera vez. Si el laboratorio está operativo, ve directamente a **Pruebas por capa**, **Wireshark en Cursor** o **Comandos de demostración**.

## 1. Preparar OrbStack y conectar Cursor

En el Mac, inicia OrbStack. Para una instalación nueva, crea desde *Linux Machines* una máquina Ubuntu ARM64 con el nombre `mpls-node`. Se requiere acceso de administrador en esa VM y conexión para descargar las herramientas y las imágenes. En macOS, abre una terminal:

```bash
orb -m mpls-node
```

En Cursor instala la extensión de acceso remoto SSH. Desde la paleta de comandos (`Cmd+Shift+P`), elige **Remote-SSH: Connect to Host** y selecciona tu alias `mpls-orb`. Para una máquina nueva, OrbStack también permite conectarse desde el Mac con `ssh mpls-node@orb`. Abre la carpeta del repositorio en la ventana remota e instala **Containerlab** (`srl-labs.vscode-containerlab`) en el host SSH cuando el editor lo solicite. [Acceso SSH a OrbStack](https://docs.orbstack.dev/machines/ssh) · [Extensión Containerlab](https://marketplace.visualstudio.com/items?itemName=srl-labs.vscode-containerlab)

**Verificación.** En la terminal integrada, `hostname` debe identificar a `mpls-node`; `uname -sm` debe mostrar Linux y, en esta VM del M1, arquitectura `aarch64`.

## 2. Preparar Docker, Containerlab y el kernel de Linux

**Docker Engine.** Si `sudo docker ps` ya funciona dentro de la VM, continúa con Containerlab. En una VM Ubuntu nueva con systemd:

```bash
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sudo sh /tmp/get-docker.sh
sudo systemctl enable --now docker
sudo systemctl is-active docker
sudo docker version
sudo docker ps
```

**Verificación.** El servicio devuelve `active`, la versión muestra cliente y servidor, y `docker ps` imprime una tabla, aunque aún esté vacía. [Instalación de Docker Engine](https://docs.docker.com/engine/install/ubuntu/)

**Containerlab.** Consulta la versión instalada y ejecuta el instalador solo si falta el comando.

```bash
if ! command -v containerlab >/dev/null; then
  curl -fsSL https://get.containerlab.dev -o /tmp/install-containerlab.sh &&
    sudo bash /tmp/install-containerlab.sh
fi
containerlab version
```

**Verificación.** Debe imprimirse la versión. Anótala si vas a reproducir la demostración en otra máquina. [Instalación de Containerlab](https://containerlab.dev/install/)

**Soporte MPLS y VRF.** Los cinco contenedores usan el kernel Linux de la VM. En un kernel modular, carga las funciones en la VM antes de desplegar:

```bash
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
sudo modprobe vrf
sysctl net.mpls.platform_labels
```

**Verificación.** El último comando debe devolver un número. El valor `0` en la VM puede ser normal: el YAML configura la tabla en el espacio de red de cada router. Si `modprobe` indica que falta un módulo, comprueba si el kernel lo integra directamente. Si tampoco existe el sysctl MPLS o el despliegue rechaza `type vrf`, registra `uname -r` y el error. En un kernel que usa módulos cargables, para repetir la carga tras reiniciar la VM:

```bash
printf '%s\n' mpls_router mpls_iptunnel vrf | sudo tee /etc/modules-load.d/mpls-corp.conf
```

## 3. Qué despliega el proyecto

Desde la terminal de Cursor, sitúate en la carpeta que contiene el YAML. En el equipo del laboratorio:

```bash
cd "/Users/oliverolvera/Documents/GitHub - Personal/L3VPN-over-MPLS/MPLS-CORP"
ls mpls-corp.clab.yml configs/{pe1,p,pe2}/{daemons,frr.conf}
```

| Enlace | Extremo A | Extremo B | Función |
|---|---|---|---|
| CE1–PE1 | CE1 eth1 · 192.168.1.1/31 | PE1 eth1 · 192.168.1.0/31 | Acceso IP en CUST |
| PE1–P | PE1 eth2 · 10.0.12.0/31 | P eth1 · 10.0.12.1/31 | Tránsito OSPF/LDP |
| P–PE2 | P eth2 · 10.0.23.0/31 | PE2 eth1 · 10.0.23.1/31 | Tránsito OSPF/LDP |
| PE2–CE2 | PE2 eth2 · 192.168.2.0/31 | CE2 eth1 · 192.168.2.1/31 | Acceso IP en CUST |

- **Infraestructura.** [mpls-corp.clab.yml](mpls-corp.clab.yml) crea tres contenedores FRRouting y dos Alpine. Monta los archivos de cada router y activa el reenvío IPv4, el espacio de etiquetas y la recepción MPLS en sus interfaces de núcleo. En los PE también habilita MPLS en la loopback. La interfaz de gestión es eth0. Las IP de gestión que muestra Containerlab son independientes del direccionamiento de la tabla.
- **OSPF y LDP.** [PE1](configs/pe1/frr.conf), [P](configs/p/frr.conf) y [PE2](configs/pe2/frr.conf) anuncian sus loopbacks 10.255.255.1, .2 y .3 como /32 en el área 0. OSPF calcula el camino. LDP utiliza esas loopbacks para sus sesiones y distribuye las etiquetas de transporte. En cada archivo `daemons` se activan ospfd y ldpd.
- **VRF y sucursales.** El YAML crea CUST con la tabla 100 en cada PE, incorpora la interfaz hacia el CE y configura el /31. En FRR, una ruta estática por VRF apunta a la LAN local a través del CE. Alpine representa cada LAN con una IP de loopback y tiene una ruta específica hacia la LAN remota por eth1. En un /31 ambas direcciones del enlace son utilizables.
- **MP-BGP.** Solo los PE ejecutan bgpd. Usan iBGP en el AS 65000 desde sus loopbacks y activan la familia IPv4 VPN. En CUST redistribuyen rutas conectadas y estáticas. El RD `65000:1` forma parte de los prefijos VPNv4; el RT compartido `65000:100` determina qué rutas importar. Zebra asigna la etiqueta VPN solicitada por `label vpn export auto`. P reenvía por etiqueta de transporte.
- **Persistencia.** El YAML y `configs/` son las entradas de un despliegue limpio. La carpeta `clab-mpls-corp/` contiene estado generado. El archivo de anotaciones conserva la disposición del dibujo. Los números de etiqueta pueden variar entre ejecuciones. Las imágenes del YAML usan el tag `latest`; anota también la versión efectiva de FRR con `sudo docker exec clab-mpls-corp-p vtysh -c 'show version'`.

## 4. Desplegar y visualizar la topología

```bash
sudo containerlab deploy -t mpls-corp.clab.yml
sudo containerlab inspect -t mpls-corp.clab.yml
```

**Verificación.** Deben aparecer cinco nodos en `running`: clab-mpls-corp-ce1, ce2, pe1, p y pe2 con el mismo prefijo. Revisa también el resultado de los comandos de creación de CUST y las interfaces. Los protocolos necesitan unos segundos para formar sus sesiones.

**Desde Cursor.** Abre la vista Containerlab, despliega el laboratorio en ejecución y abre su topología. Deben verse cuatro enlaces y el recorrido CE1–PE1–P–PE2–CE2. El dibujo puede aparecer invertido horizontalmente. Los nombres de nodo e interfaz identifican cada enlace.

**Desde el navegador.** Dentro de la VM ejecuta:

```bash
sudo containerlab graph -t mpls-corp.clab.yml
```

Abre [el visor en el Mac](http://localhost:50080) o [el dominio de la VM](http://mpls-node.orb.local:50080). Deja esa terminal abierta y usa otra para las pruebas. Para cerrar el visor presiona Ctrl+C en su terminal. Si prefieres dejarlo en segundo plano, ejecuta el comando con `&` al final; en esa misma terminal usa `jobs`, recupera el trabajo con `fg %N` (sustituye N por su número) y presiona Ctrl+C. [Visor de Containerlab](https://containerlab.dev/cmd/graph/)

## 5. Pruebas por capa

Ejecuta las pruebas en orden. Así, si un ping falla, podrás distinguir una falta de conectividad en el núcleo de una ruta VPN que todavía no se ha importado.

### A. OSPF y alcanzabilidad del núcleo

```bash
sudo docker exec clab-mpls-corp-p vtysh -c 'show daemons' -c 'show ip ospf neighbor'
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show ip route 10.255.255.3/32'
sudo docker exec clab-mpls-corp-pe1 ping -c 4 -I 10.255.255.1 10.255.255.3
```

**Verificación.** P ve a .1 y .3 en Full. PE1 conoce la loopback de PE2 por OSPF vía 10.0.12.1, eth2. Las cuatro respuestas prueban también el retorno hacia la loopback de PE1.

### B. LDP y reenvío en el kernel

```bash
sudo docker exec clab-mpls-corp-p vtysh -c 'show mpls ldp discovery detail' -c 'show mpls ldp ipv4 interface' -c 'show mpls ldp neighbor'
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show mpls ldp ipv4 binding'
sudo docker exec clab-mpls-corp-pe1 ip route get 10.255.255.3 from 10.255.255.1
sudo docker exec clab-mpls-corp-p ip -f mpls route show
```

**Verificación.** En P, LSR ID 10.255.255.2:0, eth1 y eth2 ACTIVE y dos vecinos OPERATIONAL. En PE1 busca la etiqueta remota anunciada por P para 10.255.255.3/32. Debe corresponder al valor de `encap mpls` en la ruta Linux y a una entrada en P que reenvía por eth2 hacia PE2.

### C. Acceso local en la VRF

```bash
sudo docker exec clab-mpls-corp-pe1 ip -d link show CUST
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show ip route vrf CUST'
sudo docker exec clab-mpls-corp-pe2 vtysh -c 'show ip route vrf CUST'
sudo docker exec clab-mpls-corp-pe1 ping -I CUST -c 4 10.10.10.1
sudo docker exec clab-mpls-corp-pe2 ping -I CUST -c 4 10.20.20.1
```

**Verificación.** CUST usa la tabla 100. PE1 muestra la LAN 10.10.10.0/24 como estática vía 192.168.1.1; PE2 muestra 10.20.20.0/24 vía 192.168.2.1. Cada ping local debe recibir cuatro respuestas. En el laboratorio completo también aparecerán rutas remotas aprendidas por BGP.

### D. Intercambio VPNv4 e importación en CUST

```bash
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show bgp ipv4 vpn summary'
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show bgp ipv4 vpn'
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show ip route vrf CUST 10.20.20.0/24'
sudo docker exec clab-mpls-corp-pe2 vtysh -c 'show ip route vrf CUST 10.10.10.0/24'
```

**Verificación.** PE1 tiene sesión con 10.255.255.3 y un recuento positivo de prefijos recibidos. Cada PE importa la LAN remota como BGP. En el detalle de la ruta puede aparecer un salto recursivo por la loopback del PE remoto y un salto resuelto con dos etiquetas hacia P.

### E. Conectividad entre sucursales

```bash
sudo docker exec clab-mpls-corp-ce1 ip route
sudo docker exec clab-mpls-corp-ce2 ip route
sudo docker exec clab-mpls-corp-ce1 ping -c 4 -I 10.10.10.1 10.20.20.1
sudo docker exec clab-mpls-corp-ce2 ping -c 4 -I 10.20.20.1 10.10.10.1
```

**Verificación.** Cada CE envía el prefijo remoto a su PE por eth1. En la ejecución documentada ambos pings recibieron 4 de 4 respuestas. Elegir explícitamente la IP origen comprueba el camino de regreso a la LAN simulada.

## 6. Wireshark en Cursor y lectura del paquete

1. En el diagrama del laboratorio activo, haz clic derecho en **p → Capture**. Selecciona **eth1 y eth2** y elige **Wireshark VNC**. Si el diálogo lo permite, selecciona una sola ventana para ambas interfaces. También puedes iniciar la captura desde cada interfaz en el árbol del laboratorio.
2. En versiones de Containerlab anteriores a 0.83.0, o si la extensión solicita el servicio, abre la paleta y ejecuta **Install Edgeshark** en el host remoto. Docker en la VM necesita poder descargar la imagen de captura. Con VNC, Wireshark se visualiza desde el editor.
3. Espera a que la captura esté activa. En la terminal de Cursor genera tráfico de CE1 a CE2:

   ```bash
   sudo docker exec clab-mpls-corp-ce1 ping -c 4 -I 10.10.10.1 10.20.20.1
   ```

4. Detén la captura y pega este **filtro de visualización** en la barra de Wireshark:

   ```text
   mpls && icmp.type == 8 && ip.src == 10.10.10.1 && ip.dst == 10.20.20.1
   ```

5. Selecciona dos solicitudes con el mismo identificador y secuencia ICMP. Expande **Frame** para identificar la interfaz y cada **MultiProtocol Label Switching Header** para leer la pila. Guarda la captura en formato pcapng con **File → Save As**. Si Wireshark corre en VNC, comprueba dónde quedó el archivo y que puedes volver a abrirlo desde tu entorno antes de cerrar la sesión.

| Punto de observación, de A hacia B | Cabeceras que se esperan | Explicación para la presentación |
|---|---|---|
| PE1 eth1, enlace con CE1 | Ethernet → IPv4 → ICMP | El cliente envía IP. PE1 consulta CUST al recibir el paquete. |
| P eth1, entrada desde PE1 | Ethernet → MPLS transporte (S=0) → MPLS VPN (S=1) → IPv4 → ICMP | PE1 ya impuso la etiqueta VPN anunciada por PE2 y la de transporte aprendida de P. |
| P eth2, salida hacia PE2 | Ethernet → MPLS VPN (S=1) → IPv4 → ICMP | P retiró la etiqueta externa por penultimate hop popping (PHP). La interna conserva su valor. |
| PE2 eth2, enlace con CE2 | Ethernet → IPv4 → ICMP | PE2 procesó la etiqueta VPN y entregó el paquete hacia el CE en la VRF correspondiente. |

**Ejemplo de la sesión.** Las tramas 11 (106 bytes) y 9 (102 bytes) mostraron la misma solicitud con identificador 0x0028 y secuencia 0. La trama 9 se capturó en P eth2 y mostraba una sola etiqueta, 80, con S=1. Para documentar la entrada, abre la de 106 bytes, confirma eth1 y lee allí ambos valores. Una entrada MPLS ocupa cuatro bytes. El bit S identifica el fondo de la pila; el valor de la etiqueta y la interfaz permiten seguir la operación. El orden de las filas o el valor del TTL por sí solos no identifican el salto.

Para observar también los enlaces de cliente, agrega capturas en PE1 eth1 y PE2 eth2 y usa el filtro anterior quitando `mpls &&`. La comparación de los cuatro puntos documenta la imposición de la pila, PHP y la entrega IP final. [Extensión y captura](https://containerlab.dev/manual/gui/vsc-extension/) · [Campos MPLS en Wireshark](https://www.wireshark.org/docs/dfref/m/mpls.html) · [RFC 3032](https://www.rfc-editor.org/rfc/rfc3032) · [RFC 4364](https://www.rfc-editor.org/rfc/rfc4364)

## 7. Diagnóstico y arranque limpio

| Síntoma | Primera comprobación |
|---|---|
| El contenedor está en running pero los protocolos aún no tienen vecinos | Espera la convergencia y repite A y B. Comprueba los demonios en ambos extremos. |
| OSPF está en Full pero P muestra LSR ID 0.0.0.0:0 y ninguna interfaz LDP | Compara archivo montado, configuración activa y log con los comandos de abajo. |
| FRR registra Unknown command en address-family ipv4 y aparece mpls ldp-sync dentro de OSPF | Verifica el `exit` que cierra `router ospf` antes del bloque global `mpls ldp`. Esta fue la causa del fallo de arranque observado con FRR 8.4_git. |
| Aparece un aviso sobre /etc/frr/vtysh.conf | En esta imagen apareció también con las sesiones operativas. Revisa por separado el resultado del comando y los errores de procesamiento de frr.conf. |
| Funciona el ping local de la VRF pero falla entre sedes | Revisa la importación de la LAN remota en ambos PE (D), la ruta específica en ambos CE (E) y el reenvío MPLS del kernel (B). |
| Wireshark muestra cero solicitudes | Inicia la captura antes de lanzar un nuevo ping; revisa la interfaz, el sentido del filtro y si estás en un enlace con MPLS. |

```bash
sudo docker exec clab-mpls-corp-p cat /etc/frr/frr.conf
sudo docker exec clab-mpls-corp-p vtysh -c 'show running-config'
sudo docker logs clab-mpls-corp-p 2>&1 | tail -n 100
```

**Comprobar reproducibilidad sin interrumpir el principal.** En la raíz del repositorio copia el YAML y las configuraciones a un directorio temporal. Ejecuta los bloques en la misma terminal para conservar las variables.

```bash
prueba=$(mktemp -d /tmp/mpls-prueba-XXXXXX)
lab=$(basename "$prueba")
cp -R configs "$prueba/"
sed "s/^name: mpls-corp$/name: $lab/" mpls-corp.clab.yml > "$prueba/prueba.clab.yml"
sudo containerlab deploy -t "$prueba/prueba.clab.yml"
```

Tras la convergencia, valida los nodos de la copia antes de introducir ajustes manuales:

```bash
sudo docker exec "clab-$lab-p" vtysh -c 'show ip ospf neighbor' -c 'show mpls ldp neighbor'
sudo docker exec "clab-$lab-pe1" vtysh -c 'show bgp ipv4 vpn summary'
sudo docker exec "clab-$lab-ce1" ping -c 4 -I 10.10.10.1 10.20.20.1
sudo docker exec "clab-$lab-ce2" ping -c 4 -I 10.20.20.1 10.10.10.1
```

**Verificación.** Dos vecinos OSPF Full, dos LDP OPERATIONAL, prefijos VPNv4 recibidos y cuatro respuestas en cada sentido. Para retirar la instancia temporal:

```bash
sudo containerlab destroy -t "$prueba/prueba.clab.yml" --cleanup
```

Para **recrear el principal** después de cambiar los archivos fuente, usa `sudo containerlab deploy -t mpls-corp.clab.yml --reconfigure`. Esto interrumpe el tráfico y reemplaza los contenedores. Guarda la evidencia y cualquier ajuste interactivo que quieras conservar antes de hacerlo. Para **retirarlo al terminar**, ejecuta `sudo containerlab destroy -t mpls-corp.clab.yml --cleanup` desde el proyecto.

## 8. Comandos de demostración

Con el laboratorio principal convergido, ejecuta una línea a la vez. Inicia la captura en **P eth1 y eth2** antes del último ping. Este orden permite explicar quién aprende el camino, quién anuncia la LAN y qué ocurre con el paquete.

```bash
# 1. Presentar los cinco nodos y ubicar los cuatro enlaces en Cursor.
sudo containerlab inspect -t mpls-corp.clab.yml

# 2. P conoce a ambos PE por OSPF y establece dos sesiones LDP.
sudo docker exec clab-mpls-corp-p vtysh -c 'show ip ospf neighbor' -c 'show mpls ldp neighbor'

# 3. PE1 aprende la etiqueta de transporte para alcanzar la loopback de PE2.
sudo docker exec clab-mpls-corp-pe1 ip route get 10.255.255.3 from 10.255.255.1

# 4. La sesión entre PE intercambia prefijos VPNv4; CUST importa la LAN B.
sudo docker exec clab-mpls-corp-pe1 vtysh -c 'show bgp ipv4 vpn summary' -c 'show ip route vrf CUST 10.20.20.0/24'

# 5. Con Wireshark capturando, CE1 genera la solicitud que se seguirá en P.
sudo docker exec clab-mpls-corp-ce1 ping -c 4 -I 10.10.10.1 10.20.20.1
```

**Cierre de la demostración.** Señala las cuatro respuestas en la terminal. En Wireshark, elige una solicitud y muestra primero las dos etiquetas en P eth1 y después la etiqueta VPN conservada en P eth2. La coincidencia de IP, identificador y secuencia ICMP vincula las dos tramas con el mismo ping.
