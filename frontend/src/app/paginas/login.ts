import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, detalle, mensajeGeneral } from '../core/errores';
import { PROVEEDORES, ProveedorOAuth } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';

@Component({
  selector: 'app-login',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, Glifos, Marca],
  styleUrl: './acceso.css',
  template: `
    <div class="pagina acceso">
      <app-glifos [densidad]="60" />

      <section aria-label="Presentación" class="presentacion">
        <app-marca [tam]="40" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" />
        <h1 class="lema">Lo que ocurre en la red, <span class="cursiva-sangre">bajo control.</span></h1>
        <p class="entradilla">
          Umbral, la plataforma de Kaelum Security: tus incidencias, los eventos de tus sensores y cada acción, con trazabilidad completa.
        </p>
        <div class="chips">
          <span class="chip">
            <span aria-hidden="true" class="punto" [class.pulso]="apiEnLinea() !== false" [class.ok]="apiEnLinea() !== false" [class.ko]="apiEnLinea() === false"></span>
            {{ apiEnLinea() === false ? 'API sin respuesta' : 'API en línea' }}
          </span>
          <span class="chip">TLS 1.3 · HSTS</span>
          <span class="chip">Auditoría activa</span>
        </div>
      </section>

      <main class="zona-form">
        <div aria-hidden="true" class="halo"></div>
        @if (desafio()) {
          <form class="formulario" aria-labelledby="titulo-mfa" [formGroup]="formMfa" (ngSubmit)="verificar()" novalidate>
            <div class="cabecera-form">
              <span class="etiqueta-mono">PASO 2 DE 2</span>
              <h2 id="titulo-mfa">Verificación en dos pasos</h2>
            </div>
            @if (errorMfa()) {
              <div role="alert" class="aviso aviso-error"><span class="codigo">{{ errorMfa()!.codigo || 'red' }}</span><span>{{ errorMfa()!.texto }}</span></div>
            }
            <div class="campo">
              <label for="mfa-codigo">Código de tu app de autenticación</label>
              <input id="mfa-codigo" class="entrada mono" autocomplete="one-time-code" inputmode="numeric" spellcheck="false"
                aria-describedby="mfa-ayuda" formControlName="codigo" />
              <span id="mfa-ayuda" class="ayuda">¿Sin el móvil? Escribe uno de tus códigos de recuperación.</span>
            </div>
            <button type="submit" class="btn btn-sangre btn-bloque" [disabled]="enviando() || formMfa.invalid">
              {{ enviando() ? 'Verificando…' : 'Verificar' }} <span aria-hidden="true">→</span>
            </button>
            <p class="enlace-alterno"><button type="button" class="enlace-boton" (click)="volver()">← Volver a empezar</button></p>
          </form>
        } @else {
        <form class="formulario" aria-labelledby="titulo-login" [formGroup]="form" (ngSubmit)="entrar()" novalidate>
          <div class="cabecera-form">
            <span class="etiqueta-mono">ACCESO CLIENTES</span>
            <h2 id="titulo-login">Iniciar sesión</h2>
          </div>

          @if (registrado() && !error()) {
            <div role="status" class="aviso aviso-oro">
              <span class="codigo">OK</span>
              <span>Si el email era válido, tu cuenta está creada. Inicia sesión para unirte a tu empresa.</span>
            </div>
          }
          @switch (errorOAuth()) {
            @case ('oauth_email') {
              <div role="alert" class="aviso aviso-oro">
                <span class="codigo">409</span>
                <span>Ya hay una cuenta con ese email. Entra con tu contraseña y vincula la cuenta desde Mi cuenta.</span>
              </div>
            }
            @case ('oauth') {
              <div role="alert" class="aviso aviso-error">
                <span class="codigo">401</span>
                <span>No se ha podido entrar con el proveedor. Solo se aceptan cuentas con el email verificado.</span>
              </div>
            }
          }
          @if (caducada() && !error()) {
            <div role="alert" class="aviso aviso-oro">
              <span class="codigo">401</span>
              <span>Tu sesión ha terminado. Vuelve a entrar.</span>
            </div>
          }
          @switch (error()) {
            @case (401) {
              <div role="alert" class="aviso aviso-error">
                <span class="codigo">401</span><span>Email o contraseña incorrectos.</span>
              </div>
            }
            @case (null) {}
            @default {
              <div role="alert" class="aviso" [class.aviso-oro]="error() === 429" [class.aviso-error]="error() !== 429">
                <span class="codigo">{{ error() || 'red' }}</span><span>{{ mensaje() }}</span>
              </div>
            }
          }

          <div class="campo">
            <label for="email">Email</label>
            <input id="email" type="email" class="entrada" autocomplete="username" placeholder="nombre@empresa.com" formControlName="email" />
          </div>
          <div class="campo">
            <label for="contrasena">Contraseña</label>
            <input id="contrasena" type="password" class="entrada" autocomplete="current-password" placeholder="••••••••••••" formControlName="contrasena" />
          </div>

          <button type="submit" class="btn btn-sangre btn-bloque" [disabled]="enviando() || form.invalid">
            {{ enviando() ? 'Entrando…' : 'Entrar' }} <span aria-hidden="true">→</span>
          </button>
          @if (proveedores().length) {
            <div class="separador" aria-hidden="true"><span>o</span></div>
            @for (p of proveedores(); track p) {
              <a class="btn btn-suave btn-bloque" [href]="'/api/auth/oauth/' + p + '/inicio'">Continuar con {{ nombres[p] }}</a>
            }
          }
          <p class="enlace-alterno">¿Aún no tienes cuenta? <a routerLink="/registro">Crear cuenta</a></p>
        </form>
        }
        <p class="pie">Cada intento queda registrado en la auditoría</p>
        <p class="pie"><a routerLink="/">← Volver a Kaelum Security</a></p>
      </main>
    </div>
  `,
  styles: `
    .enlace-boton { background: none; border: 0; padding: 0; font: inherit; color: var(--oro-claro); cursor: pointer; text-decoration: underline; }
    .separador { display: flex; align-items: center; gap: 12px; color: var(--tenue); font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; }
    .separador::before, .separador::after { content: ''; flex: 1; height: 1px; background: rgba(255, 255, 255, 0.1); }
  `,
})
export class Login implements OnInit {
  private readonly sesion = inject(Sesion);
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  private readonly ruta = inject(ActivatedRoute).snapshot;
  private readonly parametros = this.ruta.queryParamMap;
  protected readonly nombres = PROVEEDORES;
  protected readonly proveedores = signal<ProveedorOAuth[]>([]);
  protected readonly errorOAuth = signal(this.parametros.get('error'));
  /** Contraseña (o Google/GitHub) superada y MFA pendiente. Tras OAuth llega en #mfa=… */
  protected readonly desafio = signal<string | null>(null);
  protected readonly errorMfa = signal<{ codigo: number; texto: string } | null>(null);
  protected readonly caducada = signal(this.parametros.has('caducada'));
  protected readonly registrado = signal(this.parametros.has('registrado'));
  protected readonly apiEnLinea = signal<boolean | null>(null);
  protected readonly enviando = signal(false);
  protected readonly error = signal<number | null>(null);
  protected readonly mensaje = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    contrasena: ['', Validators.required],
  });
  protected readonly formMfa = inject(FormBuilder).nonNullable.group({
    codigo: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(30)]],
  });

  ngOnInit(): void {
    this.api.salud().then(
      () => this.apiEnLinea.set(true),
      () => this.apiEnLinea.set(false),
    );
    this.api.proveedoresOAuth().then(
      (p) => this.proveedores.set(p),
      () => this.proveedores.set([]),
    );
    const fragmento = this.ruta.fragment ?? '';
    if (fragmento.startsWith('mfa=')) {
      this.desafio.set(fragmento.slice(4));
      // Fuera de la barra de direcciones y del historial: no se queda a la vista
      void this.router.navigate([], { replaceUrl: true, fragment: undefined });
    }
  }

  async entrar(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set(null);
    try {
      const { email, contrasena } = this.form.getRawValue();
      const desafio = await this.sesion.entrar(email, contrasena);
      if (desafio) {
        this.desafio.set(desafio);
        this.form.controls.contrasena.reset();
        return;
      }
      // La raíz decide: Panel (admin), Incidencias, o «Unirme a mi empresa» si está pendiente
      await this.router.navigate(['/']);
    } catch (e) {
      this.error.set(codigo(e));
      this.mensaje.set(mensajeGeneral(e));
      this.form.controls.contrasena.reset();
    } finally {
      this.enviando.set(false);
    }
  }

  async verificar(): Promise<void> {
    const desafio = this.desafio();
    if (!desafio || this.formMfa.invalid) return;
    this.enviando.set(true);
    this.errorMfa.set(null);
    try {
      await this.sesion.completarMfa(desafio, this.formMfa.getRawValue().codigo);
      await this.router.navigate(['/']);
    } catch (e) {
      const c = codigo(e);
      this.errorMfa.set({ codigo: c, texto: c === 401 ? (detalle(e) ?? 'Código incorrecto.') : mensajeGeneral(e) });
      this.formMfa.reset();
    } finally {
      this.enviando.set(false);
    }
  }

  volver(): void {
    this.desafio.set(null);
    this.errorMfa.set(null);
    this.formMfa.reset();
  }
}
