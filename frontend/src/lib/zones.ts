// Helpers puros sobre zonas. Sin DOM ni MapLibre: esto es lo que se prueba.

export const ZONAS_LIST = [
  'Centro',
  'Obispado',
  'Valle',
  'Contry',
  'Tec',
  'Fundidora',
  'Guadalupe',
  'LindaVista',
  'SanNicolas',
  'Cumbres',
  'Mitras',
  'Escobedo',
  'SantaCatarina',
  'Apodaca',
]

export type LngLat = [number, number]

export interface ZonaCentro {
  zona: string
  centro: LngLat
}

/** Distancia al cuadrado en grados. Basta para ordenar, no para medir. */
export function distSq(a: LngLat, b: LngLat): number {
  return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
}

/**
 * Las `count` zonas más cercanas a `center` que todavía no se han cargado,
 * de la más cercana a la más lejana.
 */
export function nearestZones(
  zonas: ZonaCentro[],
  center: LngLat,
  loaded: ReadonlySet<string>,
  count: number
): string[] {
  return zonas
    .map((z) => ({ zona: z.zona, dist: distSq(z.centro, center) }))
    .sort((a, b) => a.dist - b.dist)
    .filter((z) => !loaded.has(z.zona))
    .slice(0, Math.max(0, count))
    .map((z) => z.zona)
}

/** Lee los centros de un GeoJSON de zonas (`properties.zona`, `properties.centro`). */
export function zonaCentrosFromGeoJSON(geojson: {
  features: Array<{ properties: { zona: string; centro: LngLat } }>
}): ZonaCentro[] {
  return geojson.features.map((f) => ({ zona: f.properties.zona, centro: f.properties.centro }))
}

/**
 * Los archivos de calles por zona no van al repo. Sin ellos Vite responde el
 * index.html con 200, y JSON.parse truena. Solo se acepta JSON de verdad.
 */
export function isJsonResponse(res: { ok: boolean; headers: { get(k: string): string | null } }) {
  return res.ok && (res.headers.get('content-type') ?? '').includes('json')
}

export const formatNumber = (n: number) => n.toLocaleString('es-MX')
