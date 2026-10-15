import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { MINIMO_CONTRASENA, coinciden } from '../core/validadores';
import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';

@Component({
  selector: 'app-registro',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, Glifos, Marca],
  styleUrl: './acceso.css',
  template: `
    <div class="pagina acceso">
      <app-glifos [densidad]="60" />

      <section aria-label="Presentación" class="presentacion">
        <app-marca [tam]="40" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" />
        <h1 class="lema">Tu empresa ya está protegida. <span class="cursiva-sangre">Ahora, tú.</span></h1>
        <p class="entradilla">
          Crea tu cuenta y únete a tu empresa con el código de invitación que te dé su responsable. Desde ese momento podrás reportar incidencias y seguir su estado.
        </p>
        <ol class="pasos">
          <li class="paso"><span class="num">01</span><span><strong>Crea tu cuenta</strong> con tu email de trabajo.</span></li>
          <li class="paso"><span class="num">02</span><span><strong>Inicia sesión.</strong> Tu cuenta aún no ve nada: falta tu empresa.</span></li>
          <li class="paso"><span class="num">03</span><span><strong>Introduce el código</strong> que te dé el responsable de tu empresa.</span></li>
        </ol>
      </section>

      <main class="zona-form">
        <div aria-hidden="true" class="halo"></div>
        <form class="formulario" aria-labelledby="titulo-registro" [formGroup]="form" (ngSubmit)="registrar()" novalidate>
          <div class="cabecera-form">
            <span class="etiqueta-mono">NUEVA CUENTA</span>
            <h2 id="titulo-registro">Crear cuenta</h2>
          </div>

          @if (error()) {
            <div role="alert" class="aviso" [class.aviso-oro]="error() === 429" [class.aviso-error]="error() !== 429">
              <span class="codigo">{{ error() || 'red' }}</span><span>{{ mensaje() }}</span>
            </div>
          }

          <div class="campo">
            <label for="r-email">Email</label>
            <input id="r-email" type="email" class="entrada" autocomplete="username" placeholder="nombre@empresa.com" formControlName="email" />
          </div>
          <div class="campo">
            <label for="r-contrasena">Contraseña</label>
            <input id="r-contrasena" type="password" class="entrada" autocomplete="new-password" placeholder="••••••••••••" formControlName="contrasena"
              [attr.aria-describedby]="'r-ayuda'" />
            <span id="r-ayuda" class="ayuda">Mínimo {{ minimo }} caracteres. Mejor una frase larga que una palabra rara.</span>
          </div>
          <div class="campo">
            <label for="r-repetir">Repite la contraseña</label>
            <input id="r-repetir" type="password" class="entrada" autocomplete="new-password" placeholder="••••••••••••" formControlName="repetir"
              [class.invalida]="form.hasError('noCoinciden') && form.controls.repetir.dirty" />
            @if (form.hasError('noCoinciden') && form.controls.repetir.dirty) {
              <span role="alert" class="error-campo">Las contraseñas no coinciden.</span>
            }
          </div>

          <button type="submit" class="btn btn-sangre btn-bloque" [disabled]="enviando() || form.invalid">
            {{ enviando() ? 'Creando…' : 'Crear cuenta' }} <span aria-hidden="true">→</span>
          </button>
          <p class="enlace-alterno">¿Ya tienes cuenta? <a routerLink="/login">Inicia sesión</a></p>
        </form>
        <p class="pie">Tu contraseña se guarda con Argon2id: ni nosotros podemos leerla</p>
        <p class="pie"><a routerLink="/">← Volver a Kaelum Security</a></p>
      </main>
    </div>
  `,
})
export class Registro {
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  protected readonly minimo = MINIMO_CONTRASENA;
  protected readonly enviando = signal(false);
  protected readonly error = signal<number | null>(null);
  protected readonly mensaje = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group(
    {
      email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
      contrasena: ['', [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)]],
      repetir: ['', Validators.required],
    },
    { validators: coinciden('contrasena', 'repetir') },
  );

  async registrar(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set(null);
    try {
      const { email, contrasena } = this.form.getRawValue();
      await this.api.registro(email, contrasena);
      // La API responde igual exista o no el email: el login dirá si la cuenta es suya
      await this.router.navigate(['/login'], { queryParams: { registrado: 1 } });
    } catch (e) {
      this.error.set(codigo(e));
      this.mensaje.set(
        codigo(e) === 422
          ? `Revisa el email y la contraseña (mínimo ${MINIMO_CONTRASENA} caracteres).`
          : mensajeGeneral(e),
      );
    } finally {
      this.enviando.set(false);
    }
  }
}
