// Espejo de app/esquemas.py y app/modelos.py de la API.

export type Rol = 'usuario' | 'analista' | 'admin';
export type Estado = 'abierto' | 'en_analisis' | 'resuelto' | 'cerrado';
export type Severidad = 'baja' | 'media' | 'alta' | 'critica';
export type Categoria =
  | 'phishing'
  | 'malware'
  | 'acceso_no_autorizado'
  | 'fuga_datos'
  | 'denegacion_servicio'
  | 'otro';

/** GET /api/config/cliente: config web de Firebase (pública, no lleva secretos). */
export interface ConfigCliente {
  firebase: { apiKey: string; authDomain: string; projectId: string };
}

export interface Empresa {
  id: number;
  codigo: string;
  nombre: string;
  sector: string | null;
  activa: boolean;
  creada_en: string;
}

export interface EmpresaNueva {
  codigo: string;
  nombre: string;
  sector: string | null;
}

export type EmpresaEdicion = Partial<Pick<Empresa, 'nombre' | 'activa'>> & { sector?: string };

export interface Usuario {
  id: number;
  email: string;
  rol: Rol;
  /** null = personal de Kaelum (admin, analista). */
  empresa_id: number | null;
  activo: boolean;
  creado_en: string;
}

export interface Incidente {
  id: number;
  titulo: string;
  descripcion: string;
  severidad: Severidad;
  categoria: Categoria;
  estado: Estado;
  reportante_id: number;
  analista_id: number | null;
  empresa_id: number | null;
  reportante_email: string | null;
  analista_email: string | null;
  creado_en: string;
  actualizado_en: string;
  /** Solo llega para el analista asignado y el admin. */
  notas_internas?: string | null;
}

export interface IncidenteNuevo {
  titulo: string;
  descripcion: string;
  severidad: Severidad;
  categoria: Categoria;
}

export type IncidenteEdicion = Partial<Pick<Incidente, 'titulo' | 'descripcion' | 'categoria'>>;

export interface RegistroAuditoria {
  id: number;
  usuario_id: number | null;
  usuario_email: string | null;
  accion: string;
  recurso: string;
  recurso_id: number | null;
  ip: string | null;
  detalle: string | null;
  fecha: string;
}

export interface Pagina<T> {
  total: number;
  limite: number;
  desplazamiento: number;
  elementos: T[];
}

// --- Etiquetas y colores de la interfaz ---

export const ROLES: Record<Rol, string> = {
  usuario: 'Usuario',
  analista: 'Analista',
  admin: 'Admin',
};

export const ESTADOS: Record<Estado, { nombre: string; clase: string }> = {
  abierto: { nombre: 'Abierto', clase: 'est-abierto' },
  en_analisis: { nombre: 'En análisis', clase: 'est-analisis' },
  resuelto: { nombre: 'Resuelto', clase: 'est-resuelto' },
  cerrado: { nombre: 'Cerrado', clase: 'est-cerrado' },
};

export const ORDEN_ESTADOS: Estado[] = ['abierto', 'en_analisis', 'resuelto', 'cerrado'];

export const SEVERIDADES: Record<Severidad, { nombre: string; clase: string; ayuda: string }> = {
  baja: { nombre: 'Baja', clase: 'sev-baja', ayuda: 'Sin impacto en el servicio' },
  media: { nombre: 'Media', clase: 'sev-media', ayuda: 'Afecta a un equipo o usuario' },
  alta: { nombre: 'Alta', clase: 'sev-alta', ayuda: 'Afecta a un área o servicio' },
  critica: { nombre: 'Crítica', clase: 'sev-critica', ayuda: 'Datos o negocio en riesgo' },
};

export const CATEGORIAS: Record<Categoria, string> = {
  phishing: 'Phishing',
  malware: 'Malware',
  acceso_no_autorizado: 'Acceso no autorizado',
  fuga_datos: 'Fuga de datos',
  denegacion_servicio: 'Denegación de servicio',
  otro: 'Otro',
};

/** Mismo grafo que TRANSICIONES en app/servicios/incidentes.py. */
export type EstadoTriaje = 'nuevo' | 'revisado' | 'ignorado';

export const ESTADOS_TRIAJE: Record<EstadoTriaje, { nombre: string; clase: string }> = {
  nuevo: { nombre: 'Nuevo', clase: 't-nuevo' },
  revisado: { nombre: 'Revisado', clase: 't-revisado' },
  ignorado: { nombre: 'Ignorado', clase: 't-ignorado' },
};

export type TipoEvento =
  | 'sondeo_rutas'
  | 'fichero_sensible'
  | 'fuerza_bruta'
  | 'inyeccion'
  | 'recorrido_rutas'
  | 'escaner'
  | 'otro';

export const TIPOS_EVENTO: Record<TipoEvento, string> = {
  sondeo_rutas: 'Sondeo de rutas',
  fichero_sensible: 'Fichero sensible',
  fuerza_bruta: 'Fuerza bruta',
  inyeccion: 'Inyección',
  recorrido_rutas: 'Recorrido de rutas',
  escaner: 'Escáner',
  otro: 'Otro',
};

export interface EventoSeguridad {
  id: number;
  fecha: string;
  origen_ip: string;
  tipo: TipoEvento;
  severidad: Severidad;
  metodo: string;
  ruta: string;
  agente: string | null;
  servicio: string;
  empresa_id: number | null;
  detalle: string | null;
  estado_triaje: EstadoTriaje;
  nota: string | null;
  incidente_id: number | null;
}

export interface Sensor {
  servicio: string;
  empresa_id: number | null;
  total: number;
  ultimas_24h: number;
  ultimo: string;
}

export interface Recuento {
  clave: string;
  total: number;
}

export interface Tramo {
  inicio: string;
  total: number;
}

export interface ResumenEventos {
  horas: number;
  total: number;
  ultima_hora: number;
  ips_unicas: number;
  criticos: number;
  por_tipo: Recuento[];
  por_severidad: Recuento[];
  top_ips: Recuento[];
  por_minuto: Tramo[];
  por_hora: Tramo[];
}

export const TRANSICIONES: Record<Estado, Estado | null> = {
  abierto: 'en_analisis',
  en_analisis: 'resuelto',
  resuelto: 'cerrado',
  cerrado: 'abierto', // reapertura: solo admin
};

export const ACCIONES_AUDITORIA = [
  'login',
  'login_fallido',
  'logout',
  'registro',
  'crear_usuario',
  'restablecer_contrasena',
  'cambio_contrasena',
  'cambio_contrasena_fallido',
  'cambio_rol',
  'desactivar_usuario',
  'reactivar_usuario',
  'crear_admin_cli',
  'crear_incidente',
  'editar_incidente',
  'cambio_estado',
  'asignar_incidente',
  'editar_notas',
  'borrar_incidente',
  'triaje_evento',
  'crear_empresa',
  'editar_empresa',
] as const;

export const AUDITORIA_ALERTA = new Set(['login_fallido', 'reutilizacion_token', 'cambio_contrasena_fallido']);
export const AUDITORIA_PRIVILEGIO = new Set([
  'crear_usuario',
  'restablecer_contrasena',
  'cambio_rol',
  'asignar_incidente',
  'borrar_incidente',
  'desactivar_usuario',
  'reactivar_usuario',
  'crear_admin_cli',
  'crear_empresa',
  'editar_empresa',
]);

/** Opciones de un desplegable a partir de un diccionario valor → etiqueta. */
export function opciones<K extends string>(
  registro: Record<K, string | { nombre: string }>,
  clase?: (valor: K) => string,
): { valor: K; etiqueta: string; clase?: string }[] {
  return entradas(registro).map(([valor, v]) => ({
    valor,
    etiqueta: typeof v === 'string' ? v : v.nombre,
    clase: clase?.(valor),
  }));
}

/** Nombre con el que se muestra el personal propio cuando no hay empresa. */
export const SIN_EMPRESA = 'Kaelum';

export function codigoInc(id: number): string {
  return `INC-${String(id).padStart(4, '0')}`;
}

export function entradas<K extends string, V>(registro: Record<K, V>): [K, V][] {
  return Object.entries(registro) as [K, V][];
}
