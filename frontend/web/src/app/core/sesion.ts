import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { initializeApp } from '@firebase/app';
import {
  Auth,
  inMemoryPersistence,
  initializeAuth,
  signInWithEmailAndPassword,
  signOut,
} from '@firebase/auth';
import { firstValueFrom } from 'rxjs';

import { ConfigCliente, Usuario } from './modelos';

/** Errores de Firebase traducidos a códigos HTTP: el resto de la app ya sabe pintarlos. */
const CODIGOS_FIREBASE: Record<string, number> = {
  'auth/invalid-credential': 401,
  'auth/invalid-login-credentials': 401,
  'auth/wrong-password': 401,
  'auth/user-not-found': 401,
  'auth/user-disabled': 401, // igual que una contraseña mala: no se revela que la cuenta existe
  'auth/invalid-email': 401,
  'auth/too-many-requests': 429,
  'auth/network-request-failed': 0,
};

function comoHttp(error: unknown): HttpErrorResponse {
  const codigo = (error as { code?: string })?.code ?? '';
  return new HttpErrorResponse({ status: CODIGOS_FIREBASE[codigo] ?? 400, error: { detail: codigo } });
}

/**
 * Estado de la sesión, con Firebase Authentication.
 *
 * - Firebase comprueba la contraseña y emite el ID token; la API lo verifica en cada petición
 *   y decide el rol y la empresa con su propia base de datos.
 * - Persistencia EN MEMORIA: el token no se guarda ni en localStorage, ni en sessionStorage,
 *   ni en IndexedDB (lo que Firebase hace por defecto). Un XSS no encuentra nada persistente
 *   que robar. Coste: recargar la página pide entrar otra vez.
 * - El SDK renueva solo el ID token (dura una hora) mientras la pestaña sigue abierta.
 */
@Injectable({ providedIn: 'root' })
export class Sesion {
  private readonly http = inject(HttpClient);
  private auth: Auth | null = null;

  readonly usuario = signal<Usuario | null>(null);
  readonly autenticado = computed(() => this.usuario() !== null);
  readonly esAdmin = computed(() => this.usuario()?.rol === 'admin');

  /** Al arrancar la app: la config de Firebase llega de la API (no se compila en la imagen). */
  async restaurar(): Promise<void> {
    try {
      const config = await firstValueFrom(this.http.get<ConfigCliente>('/api/config/cliente'));
      const app = initializeApp(config.firebase);
      this.auth = initializeAuth(app, { persistence: inMemoryPersistence });
    } catch {
      // Sin API no hay login posible: la pantalla de acceso ya avisa de que no responde
      this.auth = null;
    }
  }

  /** ID token vigente; `forzar` pide uno nuevo a Firebase (p. ej. tras un 401). */
  async token(forzar = false): Promise<string | null> {
    const actual = this.auth?.currentUser;
    if (!actual) return null;
    try {
      return await actual.getIdToken(forzar);
    } catch {
      return null;
    }
  }

  async entrar(email: string, contrasena: string): Promise<void> {
    if (!this.auth) throw new HttpErrorResponse({ status: 0 });
    try {
      await signInWithEmailAndPassword(this.auth, email, contrasena);
    } catch (e) {
      throw comoHttp(e);
    }
    try {
      // Firebase sabe quién es; la API decide si puede entrar (cuenta activa, empresa de alta)
      // y deja la entrada en la auditoría
      await firstValueFrom(this.http.post('/api/auth/sesion', null));
      await this.cargarUsuario();
    } catch (e) {
      await signOut(this.auth);
      this.usuario.set(null);
      throw e;
    }
  }

  async cargarUsuario(): Promise<Usuario> {
    const usuario = await firstValueFrom(this.http.get<Usuario>('/api/usuarios/yo'));
    this.usuario.set(usuario);
    return usuario;
  }

  async salir(): Promise<void> {
    try {
      await firstValueFrom(this.http.post('/api/auth/salida', null));
    } catch {
      // Sin red no queda en la auditoría, pero la sesión local se cierra igual
    } finally {
      this.limpiar();
    }
  }

  limpiar(): void {
    this.usuario.set(null);
    if (this.auth) void signOut(this.auth);
  }
}
