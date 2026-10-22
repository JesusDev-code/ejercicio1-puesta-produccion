import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { Router } from '@angular/router';

import { Sesion } from '../core/sesion';
import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';
import { PanelMfa } from '../ui/panel-mfa';

/** La única pantalla del personal de Kaelum que aún no tiene MFA: su rol lo exige. */
@Component({
  selector: 'app-activar-mfa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Glifos, Marca, PanelMfa],
  styleUrl: './acceso.css',
  template: `
    <div class="pagina acceso">
      <app-glifos [densidad]="60" />

      <section aria-label="Presentación" class="presentacion">
        <app-marca [tam]="40" nombre="Kaelum" subtitulo="SECURITY · UMBRAL" />
        <h1 class="lema">Tu acceso abre <span class="cursiva-sangre">todos los clientes.</span></h1>
        <p class="entradilla">
          Como personal de Kaelum ves datos de cada empresa cliente. Por eso tu cuenta necesita un segundo factor: con la contraseña sola no basta.
        </p>
        <ol class="pasos">
          <li class="paso"><span class="num">✓</span><span><strong>Contraseña</strong> de {{ sesion.usuario()?.email }}</span></li>
          <li class="paso"><span class="num">02</span><span><strong>Activa la verificación en dos pasos</strong> con una app de autenticación.</span></li>
        </ol>
      </section>

      <main class="zona-form">
        <div aria-hidden="true" class="halo"></div>
        <app-panel-mfa (activada)="continuar()" />
        <p class="enlace-alterno"><button type="button" class="enlace-boton" (click)="salir()">Cerrar sesión</button></p>
      </main>
    </div>
  `,
  styles: `
    app-panel-mfa { width: 100%; max-width: 520px; position: relative; }
    .enlace-boton { background: none; border: 0; padding: 0; font: inherit; color: var(--oro-claro); cursor: pointer; text-decoration: underline; }
  `,
})
export class ActivarMfa {
  protected readonly sesion = inject(Sesion);
  private readonly router = inject(Router);

  async continuar(): Promise<void> {
    await this.router.navigate(['/']);
  }

  async salir(): Promise<void> {
    await this.sesion.salir();
    await this.router.navigate(['/']);
  }
}
