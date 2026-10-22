// Espejo de app/esquemas.py y app/modelos.py de la API.

export type Rol = 'usuario' | 'gestor' | 'analista' | 'admin';
export type Estado = 'abierto' | 'en_analisis' | 'resuelto' | 'cerrado';
export type Severidad = 'baja' | 'media' | 'alta' | 'critica';
export type Categoria =
  | 'phishing'
  | 'malware'
  | 'acceso_no_autorizado'
  | 'fuga_datos'
  | 'denegacion_servicio'
  | 'otro';

export interface TokenAcceso {
  token_acceso: string;
  tipo_token: string;
  expira_en_segundos: number;
}

/** Respuesta del login con MFA activo: aún no hay sesión, solo un desafío para /auth/web/mfa. */
export interface DesafioMfa {
  mfa_requerido: true;
  desafio: string;
  expira_en_segundos: number;
}

/** Alta de MFA sin confirmar. `qr`: filas de la matriz, "1" = módulo oscuro. */
export interface MfaAlta {
  secreto: string;
  uri: string;
  qr: string[];
}

export type ProveedorOAuth = 'google' | 'github';

export const PROVEEDORES: Record<ProveedorOAuth, string> = {
  google: 'Google',
  github: 'GitHub',
};

export interface Empresa {
  id: number;
  codigo: string;
  nombre: string;
  sector: string | null;
  activa: boolean;
  /** Lo reparte el gestor para que sus trabajadores se unan tras registrarse. */
  codigo_invitacion: string;
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
  /** Admin y analista: siempre null (personal de Kaelum). Usuario y gestor: su empresa. */
  empresa_id: number | null;
  activo: boolean;
  /** Recién registrada y aún sin empresa: solo puede unirse a una con su código. */
  pendiente: boolean;
  mfa_activo: boolean;
  creado_en: string;
  /** Solo en la propia cuenta (/usuarios/yo): el nombre de su empresa, o null si no tiene. */
  empresa_nombre?: string | null;
  /** Solo en la propia cuenta. False si únicamente entra con Google o GitHub. */
  tiene_contrasena?: boolean;
  /** Solo en la propia cuenta. Su rol exige MFA: no puede desactivarlo. */
  mfa_obligatorio?: boolean;
  /** Solo en la propia cuenta. Su rol exige MFA y aún no lo ha activado: solo ve su cuenta. */
  mfa_por_activar?: boolean;
  /** Solo en la propia cuenta: proveedores vinculados. */
  proveedores?: ProveedorOAuth[];
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
  gestor: 'Gestor',
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
  'registro_duplicado',
  'unirse_empresa',
  'union_empresa_fallida',
  'regenerar_codigo_invitacion',
  'crear_usuario',
  'restablecer_contrasena',
  'reutilizacion_token',
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

export const AUDITORIA_ALERTA = new Set([
  'login_fallido',
  'reutilizacion_token',
  'cambio_contrasena_fallido',
  'registro_duplicado',
  'union_empresa_fallida',
]);
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
  'regenerar_codigo_invitacion',
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
