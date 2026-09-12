# Guía de estilo del front — para agentes y humanos

Léela antes de tocar cualquier archivo en `frontend/`. Es corta a propósito: son reglas, no
sugerencias. Si una regla estorba, se discute en el chat del equipo antes de romperla.

**Regla cero: el layout existente no se rediseña.** Un pedido de "que se vea mejor" o "menos
vibecoded" es un pedido de restylar los elementos que ya existen (color, tipo, espaciado,
bordes, sombras, estados). No es licencia para inventar pantallas, mover paneles ni hacer mockups.

---

## 1. Tokens

Viven en `frontend/src/index.css` (`:root`) y vienen de `DESIGN.md` (paleta "Cupertino
Telemetry"). No se agregan colores nuevos: si hace falta uno, primero se pregunta por qué.

| Token | Valor | Uso |
|---|---|---|
| `--canvas` | `#FAF6F3` | Fondo de la app. Cálido, mate. **Tema claro, no oscuro** |
| `--surface` / `--surface-high` | `#F1EDEA` / `#EBE7E4` | Fondo del mapa, divisores internos |
| `--card` | `#FFFFFF` | Tarjetas elevadas |
| `--ink` / `--ink-2` / `--ink-3` | `#18151A` / `#3E3D41` / `#807479` | Texto: principal, secundario, apagado |
| `--plum` | `#684959` | **La marca.** Botón primario, marcador del repartidor, logo |
| `--emerald` | `#10B981` | **Solo dinero y turno activo.** Contador de ganancias, entregas hechas |
| `--amber` | `#F59E0B` | **Solo urgencia.** Surge, zona congestionada, tiempo por vencer |
| `--indigo` | `#4F46E5` | **Solo el algoritmo.** Ruta, geocerca de regreso factible, decisión |
| `--hairline` | `#D8CCCA` | Bordes de 1px. Sombras teñidas de ciruela, nunca negro puro |

Cada color operativo tiene **un** significado. Verde no es "éxito genérico": es dinero. Si un
elemento no es dinero, urgencia ni algoritmo, va en tinta o ciruela.

## 2. Tipografía

- **Outfit**, una sola familia, pesos 400/500/600/700. Cargada desde Google Fonts en `index.html`.
- Números que cambian en vivo (contadores, reloj, minutos) llevan cifras tabulares: clase `.num`.
  Sin esto el layout tiembla cada vez que cambia un dígito.
- Etiquetas pequeñas en mayúsculas: clase `.caps` (10px, 600, tracking 0.15em). Es el **único**
  lugar donde el tracking se abre. Los títulos grandes llevan tracking negativo (−0.02em).
- Escala: 10 / 12 / 13 / 14 / 16 / 18 / 22 / 32 px. No se inventan tamaños intermedios.

## 3. Forma y elevación

- Radios: chips y badges 8px, campos 12px, tarjetas 16px, paneles 24px, botones píldora.
- Botones e inputs miden **44px mínimo**: se usan con el pulgar sobre una moto.
- Tres niveles de elevación y nada más:
  1. Canvas plano.
  2. Tarjeta: blanco + hairline + `--shadow-card`. **Sin hover.** Una tarjeta no es un botón.
  3. Isla flotante sobre el mapa: `--glass` + blur 16px + `--shadow-float`. Solo para lo que
     de verdad flota sobre el mapa (logo, píldoras inferiores, controles del mapa).
- Estados obligatorios en todo lo interactivo: hover, active (`scale(0.96)`), `focus-visible`
  (anillo `--focus-ring`), disabled. Si un control no tiene los cuatro, no está terminado.

## 4. Iconos

- SVG en línea, trazo 1.8, `stroke-linecap: round`, cuadrícula de 24px, `currentColor`.
- Viven en el objeto `Icon` de `App.tsx`. Se agrega ahí, con el mismo estilo.
- **Nunca emoji.** Ni en botones, ni en píldoras, ni en popups, ni en títulos.

## 5. Mapa

- Claro. Calles blancas sobre `#EFEAE6`; autopistas amarillo suave (`#F3DFA2`) con borde.
  De local a autopista cada nivel es más ancho y más blanco. Las vías grandes llevan casing.
- Zonas en **un** tono (ciruela, 5% de opacidad, línea punteada). Ámbar solo si la zona es
  insegura de noche. Catorce zonas no son catorce colores.
- Ruta en índigo con casing blanco. Sin glow, sin blur, sin animación de pulso.
- Marcadores: círculo relleno = origen, anillo = destino. Clases `.marker` / `.marker.is-destination`.
- Popups blancos con hairline, texto en tinta, etiquetas con clase `.muted`.

## 6. Copy

- UI en **inglés** (decisión del track de ElevenLabs). Código y docs en español.
- Frases cortas, en la voz de un repartidor con experiencia, no de un dashboard corporativo.
  "Skip it. 22 minutes there and 26 back." sí. "Route optimization declined." no.
- Números con unidad pegada y en tinta apagada: `<span>km</span>` dentro del `.route-stat`.

## 7. Prohibido

Son las marcas de UI generada por IA. Los jueces las reconocen a tres metros.

- Modo oscuro por reflejo, neón, glow, fondos aurora.
- Gradientes morado→cian, gradientes en texto (`background-clip: text`), gradientes de fondo.
- Glassmorphism en todo. Solo las islas flotantes sobre el mapa.
- Emoji como ícono.
- Tarjetas dentro de tarjetas. Se separa con hairlines y espacio, no con más cajas.
- Hover que levanta (`translateY`) cosas que no se pueden clickear.
- Puntos de estado que no representan un estado definido.
- Franjas de color a la izquierda de cada bloque, cada una de un color distinto.
- Inter, Roboto, Arial, monoespaciada para números.
- Animación `bounce`/elástica. Las transiciones son 150ms, `ease-out` o la curva `--ease`.
- Estilos en línea (`style={{...}}`) en JSX. Todo va a clases en `index.css`.
- Colores hex sueltos en el JSX salvo los del mapa (MapLibre no lee variables CSS), que viven
  en las constantes `MAP_BG`, `ROUTE_COLOR` y `ROAD` al inicio de `App.tsx`.

## 8. Antes de dar por terminado un cambio de UI

1. `npm run lint`, `npm run typecheck`, `npm run format:check` pasan.
2. Se abrió en el navegador y se miró. No se confía en que "debería verse bien".
3. Sin errores en consola que no existieran antes.
4. Ningún archivo pasa de 500 líneas. Si `App.tsx` o `index.css` se acercan, se parte por
   responsabilidad (mapa / panel / tokens), no por la mitad.

Fuentes de las reglas anti-slop:
[7 Signs a UI Has Been Vibe Coded](https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui),
[AI Design Slop](https://smoothui.dev/blog/ai-design-slop),
[15 AI UI mistakes](https://gendesigns.ai/blog/ai-generated-ui-mistakes-how-to-fix),
[Making Vibe-Coded UIs Consistent](https://medium.com/design-bootcamp/making-vibe-coded-uis-beautiful-and-consistent-a2a1ba08a140).
