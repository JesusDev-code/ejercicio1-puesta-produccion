import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import {
  Categoria,
  Empresa,
  EmpresaEdicion,
  EmpresaNueva,
  Estado,
  EventoSeguridad,
  Incidente,
  IncidenteEdicion,
  IncidenteNuevo,
  Pagina,
  RegistroAuditoria,
  ResumenEventos,
  Rol,
  Sensor,
  Severidad,
  EstadoTriaje,
  TipoEvento,
  Usuario,
} from './modelos';

type Filtros = Record<string, string | number | null | undefined>;

/** Quita los filtros vacíos: la API valida los enums y rechazaría `estado=`. */
function parametros(filtros: Filtros): HttpParams {
  let p = new HttpParams();
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== null && valor !== undefined && valor !== '') p = p.set(clave, valor);
  }
  return p;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly http = inject(HttpClient);

  // --- Salud y cuentas ---

  salud(): Promise<unknown> {
    return firstValueFrom(this.http.get('/api/salud'));
  }

  crearUsuario(datos: {
    email: string;
    contrasena: string;
    rol: Rol;
    empresa_id: number | null;
  }): Promise<Usuario> {
    return firstValueFrom(this.http.post<Usuario>('/api/usuarios', datos));
  }

  restablecerContrasena(id: number, contrasena_nueva: string): Promise<unknown> {
    return firstValueFrom(this.http.patch(`/api/usuarios/${id}/contrasena`, { contrasena_nueva }));
  }

  cambiarContrasena(contrasena_actual: string, contrasena_nueva: string): Promise<unknown> {
    return firstValueFrom(
      this.http.patch('/api/usuarios/yo/contrasena', { contrasena_actual, contrasena_nueva }),
    );
  }

  // --- Incidentes ---

  incidentes(filtros: {
    estado?: Estado | '';
    severidad?: Severidad | '';
    categoria?: Categoria | '';
    empresa_id?: number | null;
    limite?: number;
    desplazamiento?: number;
  }): Promise<Pagina<Incidente>> {
    return firstValueFrom(
      this.http.get<Pagina<Incidente>>('/api/incidentes', { params: parametros(filtros) }),
    );
  }

  incidente(id: number): Promise<Incidente> {
    return firstValueFrom(this.http.get<Incidente>(`/api/incidentes/${id}`));
  }

  crearIncidente(datos: IncidenteNuevo): Promise<Incidente> {
    return firstValueFrom(this.http.post<Incidente>('/api/incidentes', datos));
  }

  editarIncidente(id: number, cambios: IncidenteEdicion): Promise<Incidente> {
    return firstValueFrom(this.http.patch<Incidente>(`/api/incidentes/${id}`, cambios));
  }

  cambiarEstado(id: number, estado: Estado): Promise<Incidente> {
    return firstValueFrom(this.http.patch<Incidente>(`/api/incidentes/${id}/estado`, { estado }));
  }

  asignar(id: number, analista_id: number): Promise<Incidente> {
    return firstValueFrom(
      this.http.patch<Incidente>(`/api/incidentes/${id}/asignar`, { analista_id }),
    );
  }

  guardarNotas(id: number, notas_internas: string): Promise<Incidente> {
    return firstValueFrom(
      this.http.patch<Incidente>(`/api/incidentes/${id}/notas`, { notas_internas }),
    );
  }

  borrarIncidente(id: number): Promise<unknown> {
    return firstValueFrom(this.http.delete(`/api/incidentes/${id}`));
  }

  // --- Administración ---

  usuarios(filtros: {
    rol?: Rol | '';
    email?: string;
    empresa_id?: number | null;
    limite?: number;
    desplazamiento?: number;
  }): Promise<Pagina<Usuario>> {
    return firstValueFrom(
      this.http.get<Pagina<Usuario>>('/api/usuarios', { params: parametros(filtros) }),
    );
  }

  cambiarRol(id: number, rol: Rol): Promise<Usuario> {
    return firstValueFrom(this.http.patch<Usuario>(`/api/usuarios/${id}/rol`, { rol }));
  }

  cambiarActivo(id: number, activo: boolean): Promise<Usuario> {
    return firstValueFrom(this.http.patch<Usuario>(`/api/usuarios/${id}/activo`, { activo }));
  }

  empresas(filtros: { activa?: boolean | null; limite?: number } = {}): Promise<Pagina<Empresa>> {
    const params = parametros({
      activa: filtros.activa === undefined || filtros.activa === null ? null : String(filtros.activa),
      limite: filtros.limite ?? 100,
    });
    return firstValueFrom(this.http.get<Pagina<Empresa>>('/api/empresas', { params }));
  }

  crearEmpresa(datos: EmpresaNueva): Promise<Empresa> {
    return firstValueFrom(this.http.post<Empresa>('/api/empresas', datos));
  }

  editarEmpresa(id: number, cambios: EmpresaEdicion): Promise<Empresa> {
    return firstValueFrom(this.http.patch<Empresa>(`/api/empresas/${id}`, cambios));
  }

  auditoria(filtros: {
    accion?: string;
    limite?: number;
    desplazamiento?: number;
  }): Promise<Pagina<RegistroAuditoria>> {
    return firstValueFrom(
      this.http.get<Pagina<RegistroAuditoria>>('/api/auditoria', { params: parametros(filtros) }),
    );
  }

  // --- Eventos de seguridad (solo admin) ---

  eventos(filtros: {
    tipo?: TipoEvento | '';
    severidad?: Severidad | '';
    origen_ip?: string;
    estado?: EstadoTriaje | '';
    empresa_id?: number | null;
    limite?: number;
    desplazamiento?: number;
  }): Promise<Pagina<EventoSeguridad>> {
    return firstValueFrom(
      this.http.get<Pagina<EventoSeguridad>>('/api/eventos', { params: parametros(filtros) }),
    );
  }

  resumenEventos(horas: number, empresa_id: number | null = null): Promise<ResumenEventos> {
    return firstValueFrom(
      this.http.get<ResumenEventos>('/api/eventos/resumen', {
        params: parametros({ horas, empresa_id }),
      }),
    );
  }

  sensores(): Promise<Sensor[]> {
    return firstValueFrom(this.http.get<Sensor[]>('/api/eventos/sensores'));
  }

  incidenteDesdeEvento(id: number): Promise<Incidente> {
    return firstValueFrom(this.http.post<Incidente>(`/api/eventos/${id}/incidente`, null));
  }

  triarEvento(id: number, cambios: { estado?: EstadoTriaje; nota?: string }): Promise<EventoSeguridad> {
    return firstValueFrom(this.http.patch<EventoSeguridad>(`/api/eventos/${id}`, cambios));
  }

  eventoDeIncidente(incidenteId: number): Promise<EventoSeguridad> {
    return firstValueFrom(this.http.get<EventoSeguridad>(`/api/eventos/por-incidente/${incidenteId}`));
  }
}
