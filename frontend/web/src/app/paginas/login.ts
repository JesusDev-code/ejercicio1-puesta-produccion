import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
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
        <form class="formulario" aria-labelledby="titulo-login" [formGroup]="form" (ngSubmit)="entrar()" novalidate>
          <div class="cabecera-form">
            <span class="etiqueta-mono">ACCESO CLIENTES</span>
            <h2 id="titulo-login">Iniciar sesión</h2>
          </div>

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
          <p class="enlace-alterno">Las cuentas las da de alta un administrador.</p>
        </form>
        <p class="pie">Cada intento queda registrado en la auditoría</p>
        <p class="pie"><a routerLink="/">← Volver a Kaelum Security</a></p>
      </main>
    </div>
  `,
})
export class Login implements OnInit {
  private readonly sesion = inject(Sesion);
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  protected readonly caducada = signal(inject(ActivatedRoute).snapshot.queryParamMap.has('caducada'));
  protected readonly apiEnLinea = signal<boolean | null>(null);
  protected readonly enviando = signal(false);
  protected readonly error = signal<number | null>(null);
  protected readonly mensaje = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    contrasena: ['', Validators.required],
  });

  ngOnInit(): void {
    this.api.salud().then(
      () => this.apiEnLinea.set(true),
      () => this.apiEnLinea.set(false),
    );
  }

  async entrar(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set(null);
    try {
      const { email, contrasena } = this.form.getRawValue();
      await this.sesion.entrar(email, contrasena);
      await this.router.navigate(['/']); // la raíz decide: Panel (admin) o Incidencias
    } catch (e) {
      this.error.set(codigo(e));
      this.mensaje.set(mensajeGeneral(e));
      this.form.controls.contrasena.reset();
    } finally {
      this.enviando.set(false);
    }
  }
}
