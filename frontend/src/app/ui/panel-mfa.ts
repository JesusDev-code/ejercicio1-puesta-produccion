import { ChangeDetectionStrategy, Component, computed, inject, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Api } from '../core/api';
import { codigo as codigoHttp, detalle, mensajeGeneral } from '../core/errores';
import { MfaAlta } from '../core/modelos';
import { Sesion } from '../core/sesion';

/** Margen blanco alrededor del QR, en módulos: el mínimo que piden los lectores (ISO 18004). */
const MARGEN = 4;

/**
 * Verificación en dos pasos de la propia cuenta: activar (contraseña → QR → código → códigos de
 * recuperación), regenerar los códigos y desactivarla.
 */
@Component({
  selector: 'app-panel-mfa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule],
  template: `
    <section aria-labelledby="mfa-titulo" class="cristal panel-mfa">
      <div class="cabecera">
        <span class="etiqueta-mono">VERIFICACIÓN EN DOS PASOS</span>
        <h2 id="mfa-titulo" class="titulo-2 grande">{{ activo() ? 'Activada' : 'Sin activar' }}</h2>
      </div>

      @if (error()) {
        <div role="alert" class="aviso" [class.aviso-error]="error()!.codigo !== 429" [class.aviso-oro]="error()!.codigo === 429">
          <span class="codigo">{{ error()!.codigo || 'red' }}</span><span>{{ error()!.texto }}</span>
        </div>
      }
      @if (aviso()) {
        <div role="status" class="aviso aviso-ok">{{ aviso() }}</div>
      }

      @if (codigos(); as lista) {
        <p class="texto">
          <strong>Guarda estos códigos ahora:</strong> no se vuelven a mostrar. Cada uno sirve una vez para entrar si pierdes el móvil.
        </p>
        <ol class="codigos mono" aria-label="Códigos de recuperación">
          @for (c of lista; track c) { <li>{{ c }}</li> }
        </ol>
        <div class="pie">
          <button type="button" class="btn btn-suave" (click)="copiar(lista)">{{ copiado() ? 'Copiados' : 'Copiar' }}</button>
          <button type="button" class="btn btn-sangre" (click)="cerrarCodigos()">Ya los he guardado</button>
        </div>
      } @else if (alta(); as a) {
        <p class="texto">Escanea el código con tu app de autenticación (Google Authenticator, Aegis, 1Password…) y escribe el código de 6 dígitos que te muestre.</p>
        <div class="alta">
          <svg class="qr" role="img" aria-label="Código QR para la app de autenticación" shape-rendering="crispEdges"
            [attr.viewBox]="'0 0 ' + lado() + ' ' + lado()">
            <rect [attr.width]="lado()" [attr.height]="lado()" fill="#fff" />
            <path [attr.d]="trazado()" fill="#000" />
          </svg>
          <div class="manual">
            <span class="ayuda">¿No puedes escanear? Introduce esta clave:</span>
            <code class="mono secreto">{{ agrupado(a.secreto) }}</code>
          </div>
        </div>
        <form class="formulario" [formGroup]="formCodigo" (ngSubmit)="activar()" novalidate>
          <div class="campo">
            <label for="mfa-codigo-alta">Código de la app</label>
            <input id="mfa-codigo-alta" class="entrada mono" inputmode="numeric" autocomplete="one-time-code" maxlength="6" formControlName="codigo" />
          </div>
          <div class="pie">
            <button type="button" class="btn btn-texto" (click)="cancelar()">Cancelar</button>
            <button type="submit" class="btn btn-sangre" [disabled]="formCodigo.invalid || enviando()">Activar</button>
          </div>
        </form>
      } @else if (!activo()) {
        <p class="texto">Además de la contraseña, pide un código de tu móvil al entrar. Si alguien consigue tu contraseña, sin el móvil no entra.</p>
        <form class="formulario" [formGroup]="formContrasena" (ngSubmit)="iniciar()" novalidate>
          @if (tieneContrasena()) {
            <div class="campo">
              <label for="mfa-pass">Confirma tu contraseña</label>
              <input id="mfa-pass" type="password" class="entrada" autocomplete="current-password" formControlName="contrasena" />
            </div>
          }
          <div class="pie">
            <button type="submit" class="btn btn-sangre" [disabled]="(tieneContrasena() && formContrasena.invalid) || enviando()">Activar verificación</button>
          </div>
        </form>
      } @else {
        <p class="texto">Al entrar se te pide un código de tu app de autenticación. Si pierdes el móvil, usa un código de recuperación.</p>
        <form class="formulario" [formGroup]="formGestion" novalidate>
          @if (tieneContrasena() && !obligatorio()) {
            <div class="campo">
              <label for="mfa-pass-gestion">Contraseña (para desactivar)</label>
              <input id="mfa-pass-gestion" type="password" class="entrada" autocomplete="current-password" formControlName="contrasena" />
            </div>
          }
          <div class="campo">
            <label for="mfa-codigo">Código de la app o de recuperación</label>
            <input id="mfa-codigo" class="entrada mono" autocomplete="one-time-code" formControlName="codigo" />
          </div>
          <div class="pie">
            <button type="button" class="btn btn-suave" [disabled]="formGestion.controls.codigo.invalid || enviando()" (click)="regenerar()">Nuevos códigos de recuperación</button>
            @if (obligatorio()) {
              <span class="ayuda">Tu rol exige la verificación en dos pasos.</span>
            } @else {
              <button type="button" class="btn btn-peligro" [disabled]="formGestion.invalid || enviando()" (click)="desactivar()">Desactivar</button>
            }
          </div>
        </form>
      }
    </section>
  `,
  styles: `
    .panel-mfa { border-radius: 24px; padding: 30px; display: flex; flex-direction: column; gap: 18px; }
    .cabecera { display: flex; flex-direction: column; gap: 6px; }
    .grande { font-size: 28px; }
    .texto { font-size: 14px; line-height: 1.6; color: var(--apagado); }
    .formulario { display: flex; flex-direction: column; gap: 16px; }
    .pie { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: flex-end; }
    .alta { display: flex; flex-wrap: wrap; gap: 20px; align-items: center; }
    .qr { width: 184px; height: 184px; border-radius: 12px; flex: none; }
    .manual { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
    .secreto { font-size: 13px; overflow-wrap: anywhere; user-select: all; }
    .codigos { margin: 0; padding-left: 28px; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px 20px; font-size: 14px; }
    @media (max-width: 720px) { .panel-mfa { padding: 22px; } }
  `,
})
export class PanelMfa {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);

  /** Al cerrar los códigos de recuperación tras activarla (la página de activación sigue). */
  readonly activada = output<void>();

  protected readonly activo = computed(() => this.sesion.usuario()?.mfa_activo === true);
  protected readonly tieneContrasena = computed(() => this.sesion.usuario()?.tiene_contrasena !== false);
  protected readonly obligatorio = computed(() => this.sesion.usuario()?.mfa_obligatorio === true);

  protected readonly alta = signal<MfaAlta | null>(null);
  protected readonly codigos = signal<string[] | null>(null);
  protected readonly enviando = signal(false);
  protected readonly copiado = signal(false);
  protected readonly aviso = signal<string | null>(null);
  protected readonly error = signal<{ codigo: number; texto: string } | null>(null);
  private recienActivada = false;

  private readonly fb = inject(FormBuilder).nonNullable;
  protected readonly formContrasena = this.fb.group({ contrasena: ['', Validators.required] });
  protected readonly formCodigo = this.fb.group({
    codigo: ['', [Validators.required, Validators.pattern(/^\d{6}$/)]],
  });
  protected readonly formGestion = this.fb.group({
    contrasena: [''],
    codigo: ['', [Validators.required, Validators.minLength(6), Validators.maxLength(30)]],
  });

  protected readonly lado = computed(() => (this.alta()?.qr.length ?? 0) + MARGEN * 2);
  /** Todo el QR en un único <path>: un cuadrado de 1×1 por módulo oscuro. */
  protected readonly trazado = computed(() => {
    const filas = this.alta()?.qr ?? [];
    let d = '';
    filas.forEach((fila, y) => {
      for (let x = 0; x < fila.length; x++) {
        if (fila[x] === '1') d += `M${x + MARGEN} ${y + MARGEN}h1v1h-1z`;
      }
    });
    return d;
  });

  protected agrupado(secreto: string): string {
    return secreto.replace(/(.{4})/g, '$1 ').trim();
  }

  private contrasena(valor: string): string | null {
    return this.tieneContrasena() ? valor : null;
  }

  private async intentar(fn: () => Promise<void>, textos: Partial<Record<number, string>> = {}): Promise<void> {
    this.enviando.set(true);
    this.error.set(null);
    this.aviso.set(null);
    try {
      await fn();
    } catch (e) {
      const c = codigoHttp(e);
      this.error.set({ codigo: c, texto: textos[c] ?? mensajeGeneral(e) });
    } finally {
      this.enviando.set(false);
    }
  }

  async iniciar(): Promise<void> {
    await this.intentar(
      async () => {
        this.alta.set(await this.api.iniciarMfa(this.contrasena(this.formContrasena.getRawValue().contrasena)));
        this.formContrasena.reset();
      },
      // 403: cuenta sin contraseña cuyo login tiene más de 5 minutos
      { 422: 'La contraseña no es correcta.', 403: 'Vuelve a iniciar sesión para confirmar que eres tú: cierra sesión y entra de nuevo.' },
    );
  }

  async activar(): Promise<void> {
    await this.intentar(
      async () => {
        const r = await this.api.activarMfa(this.formCodigo.getRawValue().codigo);
        this.alta.set(null);
        this.formCodigo.reset();
        this.codigos.set(r.codigos);
        this.recienActivada = true;
        await this.sesion.cargarUsuario();
      },
      { 422: 'Código incorrecto. Comprueba que la hora del móvil es la correcta.' },
    );
  }

  async regenerar(): Promise<void> {
    await this.intentar(
      async () => {
        const r = await this.api.regenerarCodigosMfa(this.formGestion.getRawValue().codigo);
        this.formGestion.reset();
        this.codigos.set(r.codigos);
      },
      { 401: 'Código incorrecto.' },
    );
  }

  async desactivar(): Promise<void> {
    const { contrasena, codigo } = this.formGestion.getRawValue();
    await this.intentar(
      async () => {
        await this.api.desactivarMfa(this.contrasena(contrasena), codigo);
        this.formGestion.reset();
        await this.sesion.cargarUsuario();
        this.aviso.set('Verificación en dos pasos desactivada.');
      },
      { 401: 'Código incorrecto.', 422: 'La contraseña no es correcta.' },
    );
  }

  cancelar(): void {
    this.alta.set(null);
    this.formCodigo.reset();
  }

  async copiar(lista: string[]): Promise<void> {
    try {
      await navigator.clipboard.writeText(lista.join('\n'));
      this.copiado.set(true);
    } catch {
      // Sin permiso de portapapeles: se quedan a la vista para copiarlos a mano
    }
  }

  cerrarCodigos(): void {
    this.codigos.set(null);
    this.copiado.set(false);
    if (this.recienActivada) {
      this.recienActivada = false;
      this.aviso.set('Verificación en dos pasos activada.');
      this.activada.emit();
    }
  }
}
