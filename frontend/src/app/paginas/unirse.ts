import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { Sesion } from '../core/sesion';
import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';

/** La única pantalla de una cuenta pendiente (registrada, sin empresa todavía). */
@Component({
  selector: 'app-unirse',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, Glifos, Marca],
  styleUrl: './acceso.css',
  template: `
    <div class="pagina acceso">
      <app-glifos [densidad]="60" />

      <section aria-label="Presentación" class="presentacion">
        <app-marca [tam]="40" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" />
        <h1 class="lema">Un último paso: <span class="cursiva-sangre">tu empresa.</span></h1>
        <p class="entradilla">
          Tu cuenta ya existe, pero todavía no pertenece a ninguna empresa, así que no ve nada. Pide el código de invitación al responsable de tu empresa en Umbral.
        </p>
        <ol class="pasos">
          <li class="paso"><span class="num">✓</span><span><strong>Cuenta creada</strong> como {{ sesion.usuario()?.email }}</span></li>
          <li class="paso"><span class="num">02</span><span><strong>Únete a tu empresa</strong> con su código.</span></li>
        </ol>
      </section>

      <main class="zona-form">
        <div aria-hidden="true" class="halo"></div>
        <form class="formulario" aria-labelledby="titulo-unirse" [formGroup]="form" (ngSubmit)="unirse()" novalidate>
          <div class="cabecera-form">
            <span class="etiqueta-mono">CÓDIGO DE INVITACIÓN</span>
            <h2 id="titulo-unirse">Unirme a mi empresa</h2>
          </div>

          @if (error()) {
            <div role="alert" class="aviso" [class.aviso-oro]="error() === 429" [class.aviso-error]="error() !== 429">
              <span class="codigo">{{ error() || 'red' }}</span><span>{{ mensaje() }}</span>
            </div>
          }

          <div class="campo">
            <label for="u-codigo">Código</label>
            <input id="u-codigo" type="text" class="entrada mono" autocomplete="off" spellcheck="false" placeholder="XXXX-XXXX-XXXX"
              formControlName="codigo" aria-describedby="u-ayuda" />
            <span id="u-ayuda" class="ayuda">Da igual mayúsculas o minúsculas, y con o sin guiones.</span>
          </div>

          <button type="submit" class="btn btn-sangre btn-bloque" [disabled]="enviando() || form.invalid">
            {{ enviando() ? 'Comprobando…' : 'Unirme' }} <span aria-hidden="true">→</span>
          </button>
          <p class="enlace-alterno"><button type="button" class="enlace-boton" (click)="salir()">Cerrar sesión</button></p>
        </form>
        <p class="pie">Cada intento queda registrado en la auditoría</p>
      </main>
    </div>
  `,
  styles: `
    .enlace-boton { background: none; border: 0; padding: 0; font: inherit; color: var(--oro-claro); cursor: pointer; text-decoration: underline; }
  `,
})
export class Unirse {
  protected readonly sesion = inject(Sesion);
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  protected readonly enviando = signal(false);
  protected readonly error = signal<number | null>(null);
  protected readonly mensaje = signal('');

  protected readonly form = inject(FormBuilder).nonNullable.group({
    codigo: ['', [Validators.required, Validators.minLength(12), Validators.maxLength(30)]],
  });

  async unirse(): Promise<void> {
    if (this.form.invalid) return;
    this.enviando.set(true);
    this.error.set(null);
    try {
      this.sesion.usuario.set(await this.api.unirseAEmpresa(this.form.getRawValue().codigo));
      await this.router.navigate(['/']);
    } catch (e) {
      this.error.set(codigo(e));
      this.mensaje.set(
        codigo(e) === 422
          ? 'Ese código no es válido. Comprueba que sea el último que te han dado: si se regenera, el anterior deja de valer.'
          : mensajeGeneral(e),
      );
    } finally {
      this.enviando.set(false);
    }
  }

  async salir(): Promise<void> {
    await this.sesion.salir();
    await this.router.navigate(['/']);
  }
}
