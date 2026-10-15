import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { ROLES } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { MINIMO_CONTRASENA, coinciden } from '../core/validadores';

@Component({
  selector: 'app-cuenta',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe],
  template: `
    <div class="pila">
      <header class="textos">
        <span class="ruta">~/cuenta</span>
        <h1 class="titulo">Mi cuenta</h1>
      </header>

      <div class="columnas">
        @if (sesion.usuario(); as u) {
          <section aria-labelledby="c-datos" class="cristal tarjeta datos-cuenta">
            <div class="identidad">
              <span aria-hidden="true" class="avatar">{{ u.email.charAt(0).toUpperCase() }}</span>
              <div class="nombre">
                <h2 id="c-datos" class="email">{{ u.email }}</h2>
                <span class="pildora rol" [class]="'rol-' + u.rol">{{ rol() }}</span>
              </div>
            </div>
            <dl class="datos">
              <div><dt>Alta</dt><dd class="mono">{{ u.creado_en | date: 'dd/MM/yyyy' }}</dd></div>
              <div><dt>Estado</dt><dd class="activa"><span aria-hidden="true" class="punto"></span>Activa</dd></div>
            </dl>
            <p class="nota">El rol solo lo puede cambiar un administrador.</p>
          </section>
        }

        <section aria-labelledby="c-pass" class="cristal tarjeta seguridad">
          <div class="textos-seguridad">
            <span class="etiqueta-mono">SEGURIDAD</span>
            <h2 id="c-pass" class="titulo-2 grande">Cambiar contraseña</h2>
          </div>

          @if (exito()) {
            <div role="status" class="aviso aviso-ok">Contraseña actualizada. Se han cerrado tus sesiones en otros dispositivos.</div>
          }
          @if (error()) {
            <div role="alert" class="aviso" [class.aviso-error]="error()!.codigo !== 429" [class.aviso-oro]="error()!.codigo === 429">
              <span class="codigo">{{ error()!.codigo || 'red' }}</span><span>{{ error()!.texto }}</span>
            </div>
          }

          <form aria-labelledby="c-pass" class="formulario" [formGroup]="form" (ngSubmit)="cambiar()" novalidate>
            <div class="campo">
              <label for="c-actual">Contraseña actual</label>
              <input id="c-actual" type="password" class="entrada" autocomplete="current-password" formControlName="actual" />
            </div>
            <div class="campo">
              <label for="c-nueva">Nueva contraseña</label>
              <input id="c-nueva" type="password" class="entrada" autocomplete="new-password" aria-describedby="c-nueva-ayuda" formControlName="nueva"
                [class.invalida]="form.controls.nueva.touched && form.controls.nueva.invalid" />
              <span id="c-nueva-ayuda" class="ayuda">Mínimo 12 caracteres. Mejor una frase larga que una palabra rebuscada.</span>
            </div>
            <div class="campo">
              <label for="c-repetir">Repetir nueva contraseña</label>
              <input id="c-repetir" type="password" class="entrada" autocomplete="new-password" formControlName="repetir"
                [class.invalida]="form.hasError('noCoinciden')" />
              @if (form.hasError('noCoinciden')) { <span class="error-campo">Las contraseñas no coinciden.</span> }
            </div>
            <div class="pie">
              <span class="ayuda tenue">Al cambiarla se revocan todos tus tokens de refresco.</span>
              <button type="submit" class="btn btn-sangre" [disabled]="form.invalid || enviando()">
                {{ enviando() ? 'Actualizando…' : 'Actualizar contraseña' }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 28px; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .columnas { display: flex; flex-wrap: wrap; gap: 24px; align-items: flex-start; }
    .tarjeta { border-radius: 24px; display: flex; flex-direction: column; gap: 22px; }
    .datos-cuenta { flex: 1 1 300px; padding: 30px; }
    .seguridad {
      flex: 2 1 420px; max-width: 640px; padding: 34px;
      background: linear-gradient(165deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.02) 50%, rgba(224, 30, 60, 0.05));
    }
    .identidad { display: flex; align-items: center; gap: 16px; }
    .avatar {
      width: 64px; height: 64px; flex: none; border-radius: 50%; display: flex; align-items: center; justify-content: center;
      background: linear-gradient(140deg, #d4af6e, #7a5a26); box-shadow: 0 0 30px -6px rgba(212, 175, 110, 0.6);
      color: #1a1008; font-family: var(--serif); font-weight: 600; font-size: 30px;
    }
    .nombre { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
    .email { font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
    .rol { align-self: flex-start; padding: 3px 10px; font-weight: 700; }
    .rol-usuario { color: #f1e6e0; background: rgba(241, 230, 224, 0.09); }
    .rol-analista { color: #f0c987; background: rgba(212, 175, 110, 0.16); }
    .rol-admin { color: #ff7a88; background: rgba(224, 30, 60, 0.18); }
    .datos { margin: 0; display: flex; flex-direction: column; gap: 14px; font-size: 14px; }
    .datos div { display: flex; justify-content: space-between; gap: 12px; }
    .datos dt { color: var(--apagado); }
    .datos dd { margin: 0; }
    .datos dd.mono { font-size: 13px; }
    .activa { display: inline-flex; align-items: center; gap: 8px; color: var(--menta); font-weight: 600; }
    .nota { font-size: 13px; line-height: 1.6; color: var(--tenue); }
    .textos-seguridad { display: flex; flex-direction: column; gap: 6px; }
    .grande { font-size: 34px; }
    .formulario { display: flex; flex-direction: column; gap: 18px; }
    .pie { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between; padding-top: 6px; }
    .tenue { color: var(--tenue); max-width: 300px; }
    @media (max-width: 720px) { .seguridad, .datos-cuenta { padding: 22px; } }
  `,
})
export class Cuenta implements OnInit {
  private readonly api = inject(Api);
  protected readonly sesion = inject(Sesion);

  protected readonly rol = computed(() => {
    const r = this.sesion.usuario()?.rol;
    return r ? ROLES[r] : '';
  });
  protected readonly enviando = signal(false);
  protected readonly exito = signal(false);
  protected readonly error = signal<{ codigo: number; texto: string } | null>(null);

  protected readonly form = inject(FormBuilder).nonNullable.group(
    {
      actual: ['', Validators.required],
      nueva: ['', [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)]],
      repetir: ['', Validators.required],
    },
    { validators: coinciden('nueva', 'repetir') },
  );

  ngOnInit(): void {
    // Datos frescos: el rol o el estado pueden haber cambiado desde el login
    void this.sesion.cargarUsuario().catch(() => undefined);
  }

  async cambiar(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.exito.set(false);
    this.error.set(null);
    const { actual, nueva } = this.form.getRawValue();
    try {
      await this.api.cambiarContrasena(actual, nueva);
    } catch (e) {
      const c = codigo(e);
      this.error.set({
        codigo: c,
        texto: c === 422 ? 'La contraseña actual no es correcta.' : mensajeGeneral(e),
      });
      this.enviando.set(false);
      return;
    }
    // La API revoca TODOS los refrescos, también el de esta pestaña. Se vuelve a entrar con
    // la contraseña nueva para que la sesión actual siga viva sin pedirla otra vez.
    try {
      await this.sesion.entrar(this.sesion.usuario()!.email, nueva);
    } catch {
      // Si el login falla (p. ej. 429) la sesión dura hasta que caduque el token de acceso
    }
    this.form.reset();
    this.exito.set(true);
    this.enviando.set(false);
  }
}
