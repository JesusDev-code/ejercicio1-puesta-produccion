import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Observable, finalize, firstValueFrom, map, shareReplay } from 'rxjs';

import { TokenAcceso, Usuario } from './modelos';

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

  tokenAcceso(): string | null {
    return this.token();
  }

  async entrar(email: string, contrasena: string): Promise<void> {
    const r = await firstValueFrom(
      this.http.post<TokenAcceso>('/api/auth/web/login', { email, contrasena }),
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
