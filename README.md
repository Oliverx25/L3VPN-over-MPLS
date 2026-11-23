# L3VPN sobre MPLS

Este repositorio contiene dos laboratorios de Containerlab. Los dos arman una VPN de capa 3 sobre un backbone MPLS con FRRouting, y se despliegan por separado. El primero es la referencia corta que ya está probada. El segundo es la red empresarial que se construye a partir de esa referencia.

Los comandos se ejecutan en la VM Linux `mpls-node` de OrbStack, desde la terminal de Cursor. El kernel de macOS no reenvía MPLS.

Puedes ir directamente a la [comparación de tecnologías anteriores](#qué-cambia-para-quien-opera-la-red), la [historia del estándar](#cómo-se-llegó-al-estándar-mpls), el [glosario](#glosario-histórico-y-de-arquitectura) o las [guías de los dos proyectos](#los-dos-proyectos).

## Qué es MPLS

Imagina que dos empresas contratan al mismo operador para conectar sus sucursales. Ambas tienen un servidor de pedidos con la dirección `10.20.20.10`. Cuando llega un paquete dirigido a esa IP, ¿cómo sabe el operador a cuál servidor entregarlo? En estos laboratorios la respuesta combina dos decisiones. En el borde importa **de qué empresa llegó** el paquete. En el centro de la red importa **hasta qué router del operador debe viajar**. MPLS permite transportar ambas decisiones junto con el paquete.

**MPLS** significa *Multiprotocol Label Switching*, o conmutación mediante etiquetas multiprotocolo. Un paquete IP lleva direcciones de origen y destino. Al entrar al dominio MPLS, un router puede añadirle una o varias etiquetas cortas. Los routers que lo transportan consultan la etiqueta superior en una tabla que indica por qué interfaz reenviarlo y qué hacer con la etiqueta. El número suele tener **significado local**. Si un router recibe la etiqueta 17, lo que debe hacer con ella depende de la asignación que conoce ese router. El 17 por sí solo no identifica una empresa a escala de toda la red. [Arquitectura MPLS, RFC 3031](https://www.rfc-editor.org/rfc/rfc3031.html).

Una **clase de equivalencia de reenvío** o **FEC** agrupa paquetes que deben recibir el mismo tratamiento de reenvío. Por ejemplo, muchos destinos de clientes pueden compartir el tramo del recorrido que conduce al mismo router de salida. Llamamos **LSP** al camino que sigue en un sentido el tráfico conmutado por etiquetas. El tráfico de vuelta tiene su propia decisión de reenvío. *Multiprotocolo* alude a que la arquitectura admite distintos protocolos de red y tecnologías de enlace. Aquí el caso concreto es IPv4 sobre Ethernet. A veces se dice «capa 2.5» porque, en Ethernet, la pila de etiquetas se inserta entre la cabecera de la trama y el paquete IP. Es una descripción de la posición que puedes ver en Wireshark. [Codificación de la pila, RFC 3032](https://datatracker.ietf.org/doc/html/rfc3032).

### Seguir un pedido desde la sucursal

| Dónde está el pedido | Qué ve el equipo | Qué decisión toma |
| --- | --- | --- |
| PC y router de la sucursal (CE) | Un paquete IP dirigido al servidor | La PC lo entrega a su puerta de enlace. El CE lo encamina al operador. |
| Router de entrada del operador (PE1) | La interfaz del cliente y la IP de destino | La interfaz selecciona la tabla privada de la empresa. La ruta elegida indica el PE de salida y la etiqueta de servicio. PE1 añade esa etiqueta y encima la de transporte (*push*). |
| Núcleo del operador (routers P) | La etiqueta superior de transporte | En el camino principal empresarial, el primer P intercambia esa etiqueta por la que espera el siguiente salto (*swap*). El segundo P retira la de transporte (*pop*) y deja visible la de servicio. |
| Router de salida (PE2) | La etiqueta de servicio que él mismo anunció | Aplica el tratamiento asociado a esa etiqueta, retira la encapsulación MPLS y reenvía el paquete IP hacia el CE correspondiente. |
| Centro de datos | Un paquete IP dirigido a su servidor | El servidor recibe el pedido HTTP. La empresa A y la B pueden usar la misma URL y recibir respuestas de aplicaciones distintas. |

La **L3VPN** es el servicio de conectividad privada de capa 3 que se construye con estas piezas. La separación resulta de las tablas privadas y de las políticas de distribución de rutas. Las etiquetas permiten aplicar esas decisiones al transportar el paquete. Un operador que necesite confidencialidad frente a quien pueda capturar el enlace debe añadir cifrado. El encabezado MPLS deja el contenido disponible para su inspección, como ocurre en la captura del laboratorio. [Modelo de servicio y consideraciones de seguridad, RFC 4364](https://www.rfc-editor.org/rfc/rfc4364.html).

## Cómo se conectaban las sedes antes de MPLS

Una **sede** puede ser una sucursal, una oficina o un centro de datos. El problema histórico era darle acceso a otra sede a través de la red de un operador. Hubo varias formas de hacerlo y coexistieron. Por ejemplo, una aplicación podía enviar un paquete IP dentro de una trama de Frame Relay. IP decidía el destino entre redes y Frame Relay transportaba el paquete por un circuito virtual. Comparar ambas decisiones por separado ayuda a entender qué incorporó MPLS.

### Líneas dedicadas y PPP

La empresa podía contratar un circuito punto a punto entre la sucursal y su oficina central. Con **TDM** el operador podía reservar intervalos de tiempo recurrentes en una línea compartida para formar ese circuito. Desde los routers de la empresa, la conexión tenía dos extremos conocidos. Sobre un enlace de este tipo, **PPP** permitía establecer el enlace, negociar el transporte de IP y encapsular los paquetes. El contrato proporcionaba el circuito y PPP definía cómo hablar con el vecino. [Protocolo punto a punto, RFC 1661](https://www.rfc-editor.org/rfc/rfc1661.html).

Con diez sedes hay **45 pares** posibles: cada una se puede conectar con otras nueve y cada par se cuenta dos veces, por lo que el total es `10 × 9 / 2`. Una malla completa de circuitos directos exige esos 45 circuitos. Una estrella centrada en una sede necesita nueve, pero el tráfico entre sucursales pasa por la central y depende de su capacidad. En una L3VPN, la empresa puede conectar cada sede a un PE cercano y el operador puede ofrecer conectividad entre las diez mediante políticas de rutas. Siguen haciendo falta los accesos físicos y el dimensionamiento del núcleo.

### X.25 y los circuitos virtuales

En una red X.25, varios **circuitos virtuales** podían compartir una misma línea de acceso. «Virtual» significa que existía una asociación lógica entre extremos, aunque en el medio circulasen datos de otros usuarios. Podía tratarse de un circuito permanente provisionado de antemano o de una llamada virtual establecida cuando se necesitaba. En el acceso, el número de canal lógico indicaba a qué conexión pertenecía cada paquete. El protocolo de enlace LAPB usaba confirmaciones y retransmisiones para recuperar tramas perdidas o dañadas en ese enlace. Ese trabajo era valioso sobre líneas con errores y añadía estado y procesamiento. [Transporte de IP sobre X.25, RFC 1356](https://www.rfc-editor.org/rfc/rfc1356.html).

### Frame Relay y las tramas de longitud variable

El router de la sucursal enviaba una trama con un **DLCI**, el identificador del circuito virtual en su enlace de acceso. Por ejemplo, el operador podía asociar el DLCI 100 de una sucursal con el DLCI 205 que veía el router de la central. Ambos valores identificaban los extremos del mismo servicio y tenían significado local. Las tramas podían tener longitudes diferentes. Ante una trama dañada, la red podía descartarla y la recuperación quedaba a cargo de capas superiores, por ejemplo TCP. El parecido con MPLS es el uso de un identificador corto. La diferencia práctica para el cliente es que con Frame Relay debía organizar su enrutamiento sobre los circuitos disponibles, mientras que en la L3VPN del proyecto el PE ya conoce las redes de sus sedes. [Encapsulación sobre Frame Relay, RFC 2427](https://datatracker.ietf.org/doc/html/rfc2427).

### ATM e IP sobre ATM

**ATM** transportaba celdas de **53 bytes**, con 5 bytes de cabecera y 48 de carga útil. Los conmutadores usaban los identificadores de camino y canal virtual, **VPI/VCI**. Para transportar IP mediante **AAL5**, el emisor preparaba los datos y los dividía en bloques de 48 bytes. El receptor reunía esos bloques para recuperar el paquete. Una celda perdida podía impedir la recuperación de toda la unidad AAL5. La longitud fija facilitaba planificar la transmisión de tráfico con distintas necesidades, al precio de añadir cabeceras y, en ocasiones, relleno. [Encapsulación AAL5, RFC 2684](https://datatracker.ietf.org/doc/html/rfc2684).

Operar **IP sobre ATM** podía exigir dos mapas de la misma red. Los routers IP conocían a sus vecinos y prefijos, mientras que la red ATM mantenía los circuitos que hacían posibles esas vecindades. Un enlace que parecía directo para IP podía atravesar varios conmutadores ATM. Para diagnosticar una interrupción había que relacionar ambos mapas. Un objetivo de MPLS fue aprovechar la conmutación por identificadores y vincularla a la información de encaminamiento que manejaban los routers. [Modelos de IP sobre ATM, RFC 1932](https://datatracker.ietf.org/doc/html/rfc1932).

### IP convencional y la búsqueda de prefijo más largo

En una red IP convencional, cada router compara la dirección de destino con las redes que conoce y selecciona la coincidencia más específica. Si tiene rutas para `10.0.0.0/8` y `10.20.20.0/24`, un paquete hacia `10.20.20.10` usa la segunda. Este mecanismo sigue funcionando en las LAN y en los CE de este proyecto. La dificultad aparece cuando dos empresas usan exactamente el mismo prefijo en una sola tabla y deben llegar a servidores diferentes. Una búsqueda basada únicamente en esa dirección carece del dato «empresa de origen». Las VRF aportan ese contexto en el borde y la pila MPLS lo conserva a través del núcleo. [Reenvío IPv4, RFC 1812](https://datatracker.ietf.org/doc/html/rfc1812) y [VPN entre sedes, RFC 4364](https://www.rfc-editor.org/rfc/rfc4364.html).

### Qué cambia para quien opera la red

| Tecnología o servicio | Dato que guía el transporte | Qué implica abrir otra sucursal |
| --- | --- | --- |
| Línea dedicada | Los dos extremos del circuito contratado | Contratar otro enlace hacia la central o varios para una malla. La topología de circuitos condiciona el recorrido. |
| X.25 | El canal lógico asignado a la conexión | Añadir el acceso y establecer o provisionar los circuitos virtuales necesarios. |
| Frame Relay | El DLCI del circuito en cada acceso | Asociar los circuitos con destinos y configurar las rutas del cliente sobre ellos. |
| IP sobre ATM | El prefijo en los routers y VPI/VCI en los conmutadores | Coordinar la conectividad IP con los circuitos ATM que la sostienen. |
| IP con una tabla común | El prefijo de destino más específico | Anunciar el nuevo prefijo. Si dos clientes usan el mismo espacio, hace falta un mecanismo adicional para distinguirlos. |
| L3VPN BGP/MPLS | La VRF al entrar, la etiqueta de transporte en el núcleo y la de servicio al salir | Conectar la sede al PE, asociar su acceso con la VRF y distribuir los prefijos según la política del cliente. Los P pueden seguir ocupándose del transporte entre PE. |

## Cómo se llegó al estándar MPLS

| Fecha | Hito documentado | Aportación |
| --- | --- | --- |
| Mayo de 1996 | Ipsilon publica IFMP | Permitía pedir a un vecino que aplicara una etiqueta de enlace a un flujo IPv4 reconocido. Se exploraba cómo pasar de clasificar paquetes IP a conmutar flujos. [RFC 1953](https://www.rfc-editor.org/rfc/rfc1953.html). |
| Febrero de 1997 | Cisco describe *Tag Switching* | Separaba el control que asocia etiquetas y rutas del reenvío que consulta e intercambia esas etiquetas. Era una propuesta de fabricante. [RFC 2105](https://www.rfc-editor.org/rfc/rfc2105.html). |
| 1997 | El IETF organiza el trabajo sobre MPLS | El grupo reúne las propuestas de conmutación por etiquetas para especificar mecanismos comunes que pudieran implementar equipos de distintos fabricantes. [Mandato del grupo en 1997](https://datatracker.ietf.org/doc/charter-ietf-mpls/05/). |
| 1999 | Se documentan las VPN BGP/MPLS y los requisitos de ingeniería de tráfico | Aparecen dos aplicaciones distintas. Una distribuye rutas privadas de clientes, la otra busca controlar cómo se utilizan los recursos del núcleo. [RFC 2547](https://www.rfc-editor.org/rfc/rfc2547.html) y [RFC 2702](https://www.rfc-editor.org/rfc/rfc2702.html). |
| Enero de 2001 | Se publican la arquitectura, la codificación de la pila y la especificación inicial de LDP | Quedan descritas tres piezas que se pueden estudiar por separado: qué significa conmutar una etiqueta, cómo aparece en el enlace y cómo dos vecinos acuerdan su significado. [RFC 3031](https://www.rfc-editor.org/rfc/rfc3031.html), [RFC 3032](https://datatracker.ietf.org/doc/html/rfc3032) y [RFC 3036](https://datatracker.ietf.org/doc/html/rfc3036). |
| 2006 y 2007 | Se actualizan las especificaciones de la L3VPN y de LDP | Estas referencias explican el modelo que reproducen los laboratorios: BGP distribuye rutas VPN entre los bordes y LDP distribuye etiquetas de transporte en el núcleo. [RFC 4364](https://www.rfc-editor.org/rfc/rfc4364.html) y [RFC 5036](https://www.rfc-editor.org/rfc/rfc5036.html). |

## Cómo reconocer esas decisiones en el laboratorio

1. **¿Por dónde llega PE1 a PE2?** OSPF calcula la ruta dentro de la red del operador. En el proyecto empresarial, el camino principal usa tres enlaces de costo 10 cada uno. Si cae el enlace entre P1 y P2, queda el recorrido PE1 → P2 → PE2, cuyos enlaces suman 70. La diferencia entre 30 y 70 explica el orden de preferencia. Estos costos son métricas administrativas. Medir el tiempo de recuperación requiere observar el tráfico durante la falla.
2. **¿Qué etiqueta pide cada vecino para el transporte?** LDP anuncia asociaciones entre destinos de transporte y etiquetas. En MPLS-CORP solo hay un P, que ya es el penúltimo salto. Al capturar a ambos lados de ese P se ve pasar la pila de dos entradas a una. El segundo P del proyecto empresarial permite observar además el cambio de etiqueta externa entre saltos (*swap*).
3. **¿Cómo se distingue a los dos clientes?** Los PE intercambian rutas VPNv4 y etiquetas de servicio mediante MP-BGP. El *Route Distinguisher* permite representar anuncios distintos para un mismo prefijo IPv4. Los *Route Targets* y la política de importación determinan qué rutas incorpora cada VRF. Son tareas distintas. Dos consultas a `http://10.20.20.10:8080/pedidos`, una desde cada empresa, permiten relacionar la respuesta de cada servidor con la VRF que corresponde a su sucursal.

Para revisar una línea concreta de FRRouting, interpretar cada campo de Wireshark o seguir los archivos de una topología, consulta el [glosario de MPLS-CORP](MPLS-CORP/GLOSARIO_Y_EXPLICACION.md) y el [glosario de MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/GLOSARIO_Y_EXPLICACION.md).

## Glosario histórico y de arquitectura

| Término | Significado | Cómo interpretarlo |
| --- | --- | --- |
| WAN | *Wide Area Network*, red de área extensa | Une redes locales de sedes geográficamente separadas. |
| Backbone | Red troncal o núcleo | Infraestructura del operador compartida por muchos accesos. En este proyecto los routers P forman parte del núcleo. |
| TDM | *Time Division Multiplexing* | Varios canales comparten un medio mediante intervalos de tiempo asignados. |
| Multiplexación estadística | Compartición en función de la demanda | Cuando un usuario queda inactivo, otros pueden aprovechar capacidad. Una carga simultánea excesiva puede producir colas. |
| PPP | *Point-to-Point Protocol* | Encapsula protocolos de red en un enlace entre dos extremos. |
| VC, PVC y SVC | *Virtual Circuit*, *Permanent Virtual Circuit* y *Switched Virtual Circuit* | Un circuito virtual es una conexión lógica. El permanente suele estar preconfigurado y el conmutado se establece bajo demanda. |
| LAPB | *Link Access Procedure, Balanced* | Controla la entrega de tramas sobre el enlace de acceso X.25. |
| DLCI | *Data-Link Connection Identifier* | Número con el que una interfaz Frame Relay identifica un circuito virtual. |
| ATM y AAL5 | *Asynchronous Transfer Mode* y *ATM Adaptation Layer 5* | ATM conmuta celdas. AAL5 permite que el receptor recupere unidades de longitud variable, como un paquete IP. |
| VPI y VCI | *Virtual Path Identifier* y *Virtual Channel Identifier* | Campos de la cabecera de una celda ATM que identifican su camino y canal virtual en el enlace. |
| Overlay y modelo entre pares | Dos formas de relacionar al cliente con el operador | En el primer modelo, los routers del cliente ven conexiones lógicas entre sedes. En el modelo L3VPN, cada CE se conecta al PE local y el operador participa en el encaminamiento de la VPN. |
| Aprovisionamiento y señalización | Configuración del servicio e intercambio de mensajes de control | Asociar una interfaz a una VRF es aprovisionarla. Anunciar a un vecino la etiqueta que debe emplear es señalización. |
| IETF y RFC | *Internet Engineering Task Force* y *Request for Comments* | El IETF desarrolla especificaciones abiertas. Los RFC documentan estándares, propuestas y otros trabajos. La categoría de cada documento aclara su alcance. |
| TE | *Traffic Engineering*, ingeniería de tráfico | Busca distribuir demanda considerando los recursos y restricciones de la red. En este proyecto la preferencia de camino se configura mediante costos OSPF. |

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
| Configuración y trama, paso a paso | [Glosario de MPLS-CORP](MPLS-CORP/GLOSARIO_Y_EXPLICACION.md) | [Glosario de MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/GLOSARIO_Y_EXPLICACION.md) |

En el MacBook Air M1 conviene tener levantado un solo laboratorio. Las redes de gestión ya están separadas por si hace falta comparar los dos en la misma VM.

## Por dónde empezar

1. Preparar la VM, Docker, Containerlab y los módulos del kernel con las secciones 1 y 2 de la [guía de MPLS-CORP](MPLS-CORP/GUIA_EJECUCION_Y_PRUEBAS.md). Esa preparación sirve para los dos proyectos.
2. Desplegar y probar [MPLS-CORP](MPLS-CORP/README.md) hasta el ping entre sucursales y la captura con dos etiquetas a la entrada de P y una a la salida.
3. Seguir con [MPLS-EMPRESARIAL](MPLS-EMPRESARIAL/README.md). El diseño completo, incluidas las fases que todavía no están en el YAML, está en [el plan](MPLS-EMPRESARIAL/PLAN_MPLS_EMPRESARIAL.md).

## Qué hay en cada carpeta

```text
MPLS-CORP/
  README.md                      Qué es el laboratorio sencillo
  GLOSARIO_Y_EXPLICACION.md      Protocolos, archivos y lectura de la trama
  GUIA_EJECUCION_Y_PRUEBAS.md    Despliegue, pruebas y resultados esperados
  mpls-corp.clab.yml             Cinco nodos
  configs/                       FRR de pe1, p y pe2

MPLS-EMPRESARIAL/
  README.md                      Qué es la red de dos empresas
  GLOSARIO_Y_EXPLICACION.md      Protocolos, archivos y recorrido del pedido
  GUIA_EJECUCION_Y_PRUEBAS.md    Despliegue, pruebas y resultados esperados
  PLAN_MPLS_EMPRESARIAL.md       Diseño por fases, defensa y trabajo siguiente
  mpls-empresa.clab.yml          Doce nodos
  configs/                       FRR de pe1, p, p2 y pe2
  apps/pedidos/                  API y cliente del pedido
```

`containerlab deploy` crea `clab-mpls-corp/` o `clab-mpls-empresa/` junto al YAML. Esa carpeta es estado del despliegue, no parte del diseño.
