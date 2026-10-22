import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, finalize, firstValueFrom, map, shareReplay } from 'rxjs';

import { DesafioMfa, TokenAcceso, Usuario } from './modelos';

/**
 * Estado de la sesión.
 *
 * - El token de acceso vive SOLO en memoria (una señal): ni localStorage ni sessionStorage,
 *   para que un XSS no tenga dónde leerlo de forma persistente.
 * - El token de refresco vive en una cookie HttpOnly que pone la API (/auth/web/*). Este
 *   código nunca lo ve: por eso al recargar la página la sesión se recupera con un refresco.
 */
@Injectable({ providedIn: 'root' })
export class Sesion {
  private readonly http = inject(HttpClient);
  private readonly token = signal<string | null>(null);
  private refrescoEnCurso: Observable<string> | null = null;

  readonly usuario = signal<Usuario | null>(null);
  readonly autenticado = computed(() => this.usuario() !== null);
  readonly esAdmin = computed(() => this.usuario()?.rol === 'admin');
  readonly esGestor = computed(() => this.usuario()?.rol === 'gestor');
  /** Recién registrada y sin empresa: la consola entera le está cerrada. */
  readonly pendiente = computed(() => this.usuario()?.pendiente === true);
  /** Personal sin MFA: hasta activarlo, la consola le está cerrada. */
  readonly mfaPorActivar = computed(() => this.usuario()?.mfa_por_activar === true);

  tokenAcceso(): string | null {
    return this.token();
  }

  /**
   * Primer paso. Sin MFA, la sesión queda abierta y devuelve null. Con MFA devuelve el desafío,
   * que se completa con `completarMfa`: hasta entonces no hay ni token ni cookie.
   */
  async entrar(email: string, contrasena: string): Promise<string | null> {
    const r = await firstValueFrom(
      this.http.post<TokenAcceso | DesafioMfa>('/api/auth/web/login', { email, contrasena }),
    );
    if ('mfa_requerido' in r) return r.desafio;
    this.token.set(r.token_acceso);
    await this.cargarUsuario();
    return null;
  }

  async completarMfa(desafio: string, codigo: string): Promise<void> {
    const r = await firstValueFrom(
      this.http.post<TokenAcceso>('/api/auth/web/mfa', { desafio, codigo }),
    );
    this.token.set(r.token_acceso);
    await this.cargarUsuario();
  }

  /**
   * Un único refresco a la vez: si varias peticiones reciben 401 a la vez, todas esperan al
   * mismo. Dos refrescos en paralelo usarían la misma cookie dos veces, y la API lo trataría
   * como reutilización de un token robado y revocaría la familia entera.
   */
  refrescar(): Observable<string> {
    this.refrescoEnCurso ??= this.http.post<TokenAcceso>('/api/auth/web/refrescar', null).pipe(
      map((r) => {
        this.token.set(r.token_acceso);
        return r.token_acceso;
      }),
      finalize(() => (this.refrescoEnCurso = null)),
      shareReplay(1),
    );
    return this.refrescoEnCurso;
  }

  /** Al arrancar la app: si hay cookie de refresco válida, se recupera la sesión. */
  async restaurar(): Promise<void> {
    try {
      await firstValueFrom(this.refrescar());
      await this.cargarUsuario();
    } catch {
      this.limpiar();
    }
  }

  async cargarUsuario(): Promise<Usuario> {
    const usuario = await firstValueFrom(this.http.get<Usuario>('/api/usuarios/yo'));
    this.usuario.set(usuario);
    return usuario;
  }

  async salir(): Promise<void> {
    try {
      await firstValueFrom(this.http.post('/api/auth/web/logout', null));
    } catch {
      // Sin red la cookie no se revoca, pero la sesión local se borra igual
    } finally {
      this.limpiar();
    }
  }

  limpiar(): void {
    this.token.set(null);
    this.usuario.set(null);
  }
}
