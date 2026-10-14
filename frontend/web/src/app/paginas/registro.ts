import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { Sesion } from '../core/sesion';
import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';

export const MINIMO_CONTRASENA = 12;

export function coinciden(grupo: AbstractControl): ValidationErrors | null {
  const a = grupo.get('contrasena')?.value;
  const b = grupo.get('repetir')?.value;
  return a && b && a !== b ? { noCoinciden: true } : null;
}

@Component({
  selector: 'app-registro',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, Glifos, Marca],
  styleUrl: './acceso.css',
  styles: `
    .medidor { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 4px; }
    .segmento { height: 4px; border-radius: 999px; background: rgba(255, 255, 255, 0.08); transition: background 0.2s, box-shadow 0.2s; }
    .segmento.lleno { background: var(--oro-claro); box-shadow: 0 0 8px var(--oro-claro); }
    .segmento.lleno.ok { background: var(--menta); box-shadow: 0 0 8px var(--menta); }
    .estado-longitud { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--oro-claro); }
    .estado-longitud.ok { color: var(--menta); }
    .ayuda-pass { display: flex; flex-direction: column; gap: 8px; }
  `,
  template: `
    <div class="pagina acceso espejo">
      <app-glifos [densidad]="60" />

      <section aria-label="Presentación" class="presentacion">
        <app-marca [tam]="40" subtitulo="CONSOLA · v0.1" />
        <h1 class="lema">Reporta un incidente <span class="cursiva-sangre">en minutos.</span></h1>
        <div class="pasos">
          <p class="paso"><span class="num">01</span><span>Las cuentas nuevas se crean con rol <strong>usuario</strong>. Un administrador asigna los analistas.</span></p>
          <p class="paso"><span class="num">02</span><span>Solo verás los incidentes que tú reportes.</span></p>
          <p class="paso"><span class="num">03</span><span>Tu contraseña se guarda con argon2: nadie puede leerla, ni siquiera un administrador.</span></p>
        </div>
      </section>

      <main class="zona-form">
        <div aria-hidden="true" class="halo"></div>
        <form class="formulario" aria-labelledby="titulo-registro" [formGroup]="form" (ngSubmit)="crear()" novalidate>
          <div class="cabecera-form">
            <span class="etiqueta-mono">NUEVA CUENTA</span>
            <h2 id="titulo-registro">Crear cuenta</h2>
          </div>

          @if (error()) {
            <div role="alert" class="aviso" [class.aviso-error]="error() !== 429" [class.aviso-oro]="error() === 429">
              <span class="codigo">{{ error() }}</span><span>{{ mensaje() }}</span>
            </div>
          }

          <div class="campo">
            <label for="r-email">Email</label>
            <input id="r-email" type="email" class="entrada" autocomplete="email" placeholder="nombre@empresa.com" formControlName="email"
              [class.invalida]="form.controls.email.touched && form.controls.email.invalid" />
          </div>

          <div class="campo">
            <label for="r-pass">Contraseña</label>
            <input id="r-pass" type="password" class="entrada" autocomplete="new-password" aria-describedby="r-pass-ayuda" formControlName="contrasena"
              [class.valida]="longitud() >= minimo" [class.invalida]="longitud() > 0 && longitud() < minimo" />
            <div id="r-pass-ayuda" class="ayuda-pass">
              <div aria-hidden="true" class="medidor">
                @for (i of segmentos; track i) {
                  <div class="segmento" [class.lleno]="i < longitud()" [class.ok]="longitud() >= minimo"></div>
                }
              </div>
              <div class="estado-longitud" [class.ok]="longitud() >= minimo">
                <span>{{ longitud() >= minimo ? 'Longitud mínima cumplida' : 'Mínimo 12 caracteres' }}</span>
                <span class="mono">{{ longitud() }}/{{ minimo }}</span>
              </div>
            </div>
          </div>

          <div class="campo">
            <label for="r-pass2">Repetir contraseña</label>
            <input id="r-pass2" type="password" class="entrada" autocomplete="new-password" formControlName="repetir"
              [class.invalida]="form.hasError('noCoinciden')" aria-describedby="r-pass2-err" />
            @if (form.hasError('noCoinciden')) {
              <span id="r-pass2-err" class="error-campo">Las contraseñas no coinciden.</span>
            }
          </div>

          <button type="submit" class="btn btn-sangre btn-bloque" [disabled]="enviando() || form.invalid">
            {{ enviando() ? 'Creando…' : 'Crear cuenta' }} <span aria-hidden="true">→</span>
          </button>
          <p class="enlace-alterno">¿Ya tienes cuenta? <a routerLink="/login">Iniciar sesión</a></p>
        </form>
      </main>
    </div>
  `,
})
export class Registro {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);
  private readonly router = inject(Router);

  protected readonly minimo = MINIMO_CONTRASENA;
  protected readonly segmentos = Array.from({ length: MINIMO_CONTRASENA }, (_, i) => i);
  protected readonly enviando = signal(false);
  protected readonly error = signal<number | null>(null);
  protected readonly mensaje = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group(
    {
      email: ['', [Validators.required, Validators.email]],
      contrasena: ['', [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)]],
      repetir: ['', Validators.required],
    },
    { validators: coinciden },
  );

  private readonly contrasena = toSignal(this.form.controls.contrasena.valueChanges, { initialValue: '' });
  protected readonly longitud = computed(() => this.contrasena().length);

  async crear(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set(null);
    const { email, contrasena } = this.form.getRawValue();
    try {
      await this.api.registrar(email, contrasena);
      await this.sesion.entrar(email, contrasena);
      await this.router.navigate(['/incidentes']);
    } catch (e) {
      this.error.set(codigo(e) || 0);
      this.mensaje.set(
        codigo(e) === 409 ? 'Ese email ya tiene cuenta.' : codigo(e) === 422 ? 'Revisa el email y la contraseña.' : mensajeGeneral(e),
      );
    } finally {
      this.enviando.set(false);
    }
  }
}
