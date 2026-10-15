import { DatePipe, DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import { Empresa, ROLES, Sensor, Usuario } from '../core/modelos';
import { Sesion } from '../core/sesion';
import { MINIMO_CONTRASENA, generarContrasena } from '../core/validadores';
import { Cargando, FalloServidor } from '../ui/estados';
import { CambioPagina, Paginador } from '../ui/paginador';

const SILENCIO_MINUTOS = 15;

/** Lo que ve y gestiona el gestor (responsable) de una empresa cliente. */
@Component({
  selector: 'app-mi-empresa',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, DatePipe, DecimalPipe, Cargando, FalloServidor, Paginador],
  styleUrl: './usuarios.css',
  template: `
    <div class="pila">
      <header class="cabecera">
        <div class="textos">
          <span class="ruta">~/mi-empresa</span>
          <h1 class="titulo">{{ empresa()?.nombre ?? 'Mi empresa' }}</h1>
          <p class="subtitulo">
            Eres el responsable de tu empresa en Umbral: ves todas sus incidencias, das acceso a tus trabajadores con el código de invitación y gestionas sus cuentas.
          </p>
        </div>
      </header>

      @if (aviso(); as a) {
        <div [attr.role]="a.ok ? 'status' : 'alert'" class="aviso" [class.aviso-ok]="a.ok" [class.aviso-error]="!a.ok">
          <span>{{ a.texto }}</span>
          <button type="button" class="cerrar-aviso" aria-label="Cerrar aviso" (click)="aviso.set(null)">×</button>
        </div>
      }

      <section aria-labelledby="t-codigo" class="cristal alta">
        <div class="alta-cabecera">
          <span class="etiqueta-mono">INVITACIÓN</span>
          <h2 id="t-codigo" class="titulo-2">Código de tu empresa</h2>
        </div>
        @if (empresa(); as e) {
          <p class="ayuda">
            Tus trabajadores crean su cuenta en Umbral y, al entrar, introducen este código para unirse a tu empresa. Compártelo solo con ellos.
          </p>
          <label for="codigo-invitacion" class="solo-lector">Código de invitación</label>
          <div class="con-botones">
            <input id="codigo-invitacion" type="text" readonly class="entrada mono codigo-invitacion" [value]="e.codigo_invitacion" />
            <button type="button" class="btn btn-suave" (click)="copiar(e.codigo_invitacion)">Copiar</button>
            @if (!confirmarRegenerar()) {
              <button type="button" class="btn btn-oro" (click)="confirmarRegenerar.set(true)">Regenerar</button>
            }
          </div>
          @if (confirmarRegenerar()) {
            <div role="alert" class="aviso aviso-oro confirmacion">
              <span>El código actual dejará de valer al momento. Quien ya se unió con él sigue dentro.</span>
              <div class="acciones-alta">
                <button type="button" class="btn btn-sangre compacto" [disabled]="regenerando()" (click)="regenerar()">
                  {{ regenerando() ? 'Regenerando…' : 'Sí, regenerar' }}
                </button>
                <button type="button" class="btn btn-suave compacto" (click)="confirmarRegenerar.set(false)">Cancelar</button>
              </div>
            </div>
          }
        } @else if (falloEmpresa() !== null) {
          <app-fallo-servidor [codigo]="falloEmpresa()!" (reintentar)="cargarEmpresa()" />
        } @else {
          <app-cargando />
        }
      </section>

      <section aria-labelledby="t-trabajadores" class="cristal panel">
        <div class="alta-cabecera">
          <span class="etiqueta-mono">EQUIPO</span>
          <h2 id="t-trabajadores" class="titulo-2">Personas de tu empresa</h2>
        </div>

        @if (cargando()) {
          <app-cargando />
        } @else if (fallo() !== null) {
          <div class="relleno"><app-fallo-servidor [codigo]="fallo()!" (reintentar)="cargar()" /></div>
        } @else if (filas().length === 0) {
          <p class="vacio">Todavía no se ha unido nadie. Comparte el código de invitación.</p>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">PERSONA</th>
                  <th scope="col">ROL</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ALTA</th>
                  <th scope="col"><span class="solo-lector">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                @for (u of filas(); track u.id) {
                  <tr class="fila" [class.inactivo]="!u.activo">
                    <td>
                      <div class="usuario">
                        <span aria-hidden="true" class="avatar" [class]="'av-' + u.rol">{{ u.email.charAt(0).toUpperCase() }}</span>
                        <div class="datos">
                          <span class="email">{{ u.email }}</span>
                          <span class="mono id">#{{ u.id }}{{ esYo(u) ? ' · tú' : '' }}</span>
                        </div>
                      </div>
                    </td>
                    <td>{{ roles[u.rol] }}</td>
                    <td>
                      <span class="estado" [class.activo]="u.activo"><span aria-hidden="true" class="punto"></span>{{ u.activo ? 'Activo' : 'Desactivado' }}</span>
                    </td>
                    <td class="mono alta-fecha">{{ u.creado_en | date: 'dd/MM/yyyy' }}</td>
                    <td class="acciones">
                      @if (gestionable(u)) {
                        <button type="button" class="btn compacto btn-suave" [disabled]="ocupado() === u.id" (click)="abrirReset(u)">Contraseña</button>
                        <button type="button" class="btn compacto" [class.btn-peligro]="u.activo" [class.btn-menta]="!u.activo"
                          [disabled]="ocupado() === u.id" (click)="cambiarActivo(u)">{{ u.activo ? 'Desactivar' : 'Reactivar' }}</button>
                      } @else if (esYo(u)) {
                        <span class="ayuda">Tu cuenta: gestiónala en Mi cuenta</span>
                      } @else {
                        <span class="ayuda">Otro responsable: lo gestiona Kaelum</span>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }

        @if (total() > 0) {
          <app-paginador [total]="total()" [limite]="limite()" [desplazamiento]="desplazamiento()" (cambio)="paginar($event)" />
        }
      </section>

      <section aria-labelledby="t-sensores" class="cristal panel">
        <div class="alta-cabecera">
          <span class="etiqueta-mono">PROTECCIÓN</span>
          <h2 id="t-sensores" class="titulo-2">Sensores de tu empresa</h2>
        </div>
        @if (sensores().length === 0) {
          <p class="vacio">Tus sensores aún no han enviado ningún evento.</p>
        } @else {
          <div class="tabla-contenedor">
            <table class="tabla">
              <thead>
                <tr>
                  <th scope="col">SENSOR</th>
                  <th scope="col">ESTADO</th>
                  <th scope="col">ÚLTIMO EVENTO</th>
                  <th scope="col">24 H</th>
                </tr>
              </thead>
              <tbody>
                @for (s of sensores(); track s.servicio) {
                  <tr class="fila">
                    <td class="mono">{{ s.servicio }}</td>
                    <td>
                      <span class="estado" [class.activo]="activo(s)"><span aria-hidden="true" class="punto"></span>{{ activo(s) ? 'Enviando' : 'Silencioso' }}</span>
                    </td>
                    <td class="mono alta-fecha">{{ s.ultimo | date: 'dd/MM HH:mm:ss' }}</td>
                    <td class="mono">{{ s.ultimas_24h | number }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </section>
    </div>

    <dialog #dialogo class="dialogo" aria-labelledby="t-reset" (close)="objetivo.set(null)">
      @if (objetivo(); as u) {
        <form class="dialogo-form" (ngSubmit)="restablecer()" novalidate>
          <span class="etiqueta-mono">SEGURIDAD</span>
          <h2 id="t-reset" class="titulo-2">Restablecer contraseña</h2>
          <p class="ayuda">Para <strong class="email-objetivo">{{ u.email }}</strong>. Se cerrarán todas sus sesiones abiertas.</p>

          @if (errorReset()) {
            <div role="alert" class="aviso aviso-error">{{ errorReset() }}</div>
          }

          <div class="campo">
            <label for="r-nueva">Nueva contraseña</label>
            <div class="con-botones">
              <input id="r-nueva" class="entrada mono" autocomplete="new-password" [formControl]="nuevaContrasena"
                [type]="verReset() ? 'text' : 'password'" />
              <button type="button" class="btn btn-suave icono" [attr.aria-label]="verReset() ? 'Ocultar contraseña' : 'Mostrar contraseña'"
                [attr.aria-pressed]="verReset()" (click)="verReset.set(!verReset())">
                <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>
              </button>
              <button type="button" class="btn btn-oro" (click)="generarReset()">Generar</button>
              <button type="button" class="btn btn-suave" [disabled]="!nuevaContrasena.value" (click)="copiar(nuevaContrasena.value)">Copiar</button>
            </div>
            <span class="ayuda">Mínimo {{ minimo }} caracteres. Pásasela por un canal seguro: podrá cambiarla en Mi cuenta.</span>
          </div>

          <div class="acciones-alta">
            <button type="submit" class="btn btn-sangre" [disabled]="nuevaContrasena.invalid || enviandoReset()">
              {{ enviandoReset() ? 'Restableciendo…' : 'Restablecer' }}
            </button>
            <button type="button" class="btn btn-suave" (click)="cerrarReset()">Cancelar</button>
          </div>
        </form>
      }
    </dialog>
  `,
  styles: `
    .codigo-invitacion { flex: 1 1 auto; display: flex; align-items: center; font-size: 20px; letter-spacing: 4px; color: var(--oro-claro); }
    .confirmacion { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; }
    /* .panel no lleva relleno (la tabla va a sangre): la cabecera se alinea con la tarjeta de invitación */
    .panel > .alta-cabecera { padding: 30px 30px 10px; }
    @media (max-width: 720px) {
      .panel > .alta-cabecera { padding: 22px 22px 8px; }
    }
  `,
})
export class MiEmpresa implements OnInit {
  private readonly api = inject(Api);
  private readonly sesion = inject(Sesion);

  protected readonly roles = ROLES;
  protected readonly minimo = MINIMO_CONTRASENA;
  private readonly miId = computed(() => this.sesion.usuario()?.id);

  // --- Empresa y código ---
  protected readonly empresa = signal<Empresa | null>(null);
  protected readonly falloEmpresa = signal<number | null>(null);
  protected readonly confirmarRegenerar = signal(false);
  protected readonly regenerando = signal(false);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);

  // --- Trabajadores ---
  protected readonly filas = signal<Usuario[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly limite = signal(10);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly ocupado = signal<number | null>(null);

  // --- Sensores ---
  protected readonly sensores = signal<Sensor[]>([]);
  private consultado = Date.now();

  // --- Restablecer contraseña ---
  private readonly dialogo = viewChild.required<ElementRef<HTMLDialogElement>>('dialogo');
  protected readonly objetivo = signal<Usuario | null>(null);
  protected readonly enviandoReset = signal(false);
  protected readonly errorReset = signal<string | null>(null);
  protected readonly verReset = signal(false);
  protected readonly nuevaContrasena = new FormControl('', {
    nonNullable: true,
    validators: [Validators.required, Validators.minLength(MINIMO_CONTRASENA), Validators.maxLength(128)],
  });

  ngOnInit(): void {
    void this.cargarEmpresa();
    void this.cargar();
    void this.cargarSensores();
  }

  protected esYo(u: Usuario): boolean {
    return u.id === this.miId();
  }

  /** Lo mismo que decide la API: solo los trabajadores (rol usuario), nunca otro gestor. */
  protected gestionable(u: Usuario): boolean {
    return u.rol === 'usuario' && !this.esYo(u);
  }

  async cargarEmpresa(): Promise<void> {
    this.falloEmpresa.set(null);
    try {
      this.empresa.set(await this.api.miEmpresa());
    } catch (e) {
      this.falloEmpresa.set(codigo(e));
    }
  }

  async regenerar(): Promise<void> {
    this.regenerando.set(true);
    try {
      this.empresa.set(await this.api.regenerarMiCodigo());
      this.aviso.set({ ok: true, texto: 'Código regenerado. El anterior ya no sirve para unirse.' });
    } catch (e) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(e) });
    } finally {
      this.regenerando.set(false);
      this.confirmarRegenerar.set(false);
    }
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      const pagina = await this.api.trabajadores({
        limite: this.limite(),
        desplazamiento: this.desplazamiento(),
      });
      this.filas.set(pagina.elementos);
      this.total.set(pagina.total);
    } catch (e) {
      this.fallo.set(codigo(e));
    } finally {
      this.cargando.set(false);
    }
  }

  paginar({ desplazamiento, limite }: CambioPagina): void {
    this.desplazamiento.set(desplazamiento);
    this.limite.set(limite);
    void this.cargar();
  }

  async cargarSensores(): Promise<void> {
    try {
      this.sensores.set(await this.api.sensoresMiEmpresa());
      this.consultado = Date.now();
    } catch {
      // Sin sensores que mostrar: la sección ya lo dice y el resto de la pantalla sirve igual
    }
  }

  protected activo(s: Sensor): boolean {
    return this.consultado - new Date(s.ultimo).getTime() < SILENCIO_MINUTOS * 60_000;
  }

  async cambiarActivo(u: Usuario): Promise<void> {
    this.ocupado.set(u.id);
    this.aviso.set(null);
    try {
      const actualizado = await this.api.cambiarActivoTrabajador(u.id, !u.activo);
      this.filas.update((lista) => lista.map((x) => (x.id === actualizado.id ? actualizado : x)));
      this.aviso.set({
        ok: true,
        texto: u.activo ? `${u.email} ya no puede entrar.` : `${u.email} puede volver a entrar.`,
      });
    } catch (e) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(e) });
    } finally {
      this.ocupado.set(null);
    }
  }

  abrirReset(u: Usuario): void {
    this.objetivo.set(u);
    this.nuevaContrasena.reset();
    this.errorReset.set(null);
    this.verReset.set(false);
    this.dialogo().nativeElement.showModal();
  }

  cerrarReset(): void {
    this.dialogo().nativeElement.close();
  }

  generarReset(): void {
    this.nuevaContrasena.setValue(generarContrasena());
    this.verReset.set(true);
  }

  async restablecer(): Promise<void> {
    const u = this.objetivo();
    if (!u || this.nuevaContrasena.invalid) return;
    this.enviandoReset.set(true);
    this.errorReset.set(null);
    try {
      await this.api.restablecerContrasenaTrabajador(u.id, this.nuevaContrasena.value);
      this.cerrarReset();
      this.aviso.set({
        ok: true,
        texto: `Contraseña de ${u.email} restablecida. Sus sesiones abiertas se han cerrado.`,
      });
    } catch (e) {
      this.errorReset.set(mensajeGeneral(e));
    } finally {
      this.enviandoReset.set(false);
    }
  }

  async copiar(texto: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(texto);
      this.aviso.set({ ok: true, texto: 'Copiado al portapapeles.' });
    } catch {
      // Sin permiso de portapapeles: el texto sigue visible para copiarlo a mano
    }
  }
}
